"""
Deterministic Career Graph tree builder (Phase 1 of the star->tree
rebuild). No AI calls happen here — see Part C of the master prompt:
"The data decides the structure. The AI only names and explains."
Node labels that a later AI-naming pass (Phase 2) will shorten are
set to their real, full, non-fabricated title as an honest
placeholder (a real full O*NET title or a real official BLS SOC
group title), never invented text.
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(ROOT_DIR / "Scripts"))

from db import get_latest_inference_scores, get_latest_trait_decisions
from soc_titles import major_group, minor_group, broad_group, major_title, minor_title
from matching import match_occupations, load_career_graph, RIASEC_COLUMNS

INTEREST_TYPES_PATH = str(ROOT_DIR / "Data" / "career_interest_types.csv")

# Real O*NET RIASEC <-> Kindling axis naming (Scripts/part_a.py's own
# rename when it built Outputs/riasec_wide.csv from the real
# Occupational Interest scale) — reused here, not re-derived.
AXIS_TO_LETTER = {
    "builds_tinkers": "R",
    "investigates_why": "I",
    "creates_expresses": "A",
    "works_with_people": "S",
    "organizes_systems": "C",
    "leads_persuades": "E",
}
LETTER_TO_AXIS = {v: k for k, v in AXIS_TO_LETTER.items()}

# Real, existing copy from frontend/js/patterns.js — not re-invented
# here, just made available server-side for area-node labels.
AXIS_LABELS = {
    "builds_tinkers": "Build & tinker",
    "investigates_why": "Investigates why",
    "creates_expresses": "Create & express",
    "works_with_people": "Works with people",
    "organizes_systems": "Organizes systems",
    "leads_persuades": "Leads & persuades",
}

RIASEC_CODE_TO_LETTER = {1: "R", 2: "I", 3: "A", 4: "S", 5: "E", 6: "C"}

EVIDENCE_THRESHOLD = 0.25  # matches frontend/js/inference.js's own "Starting to appear" band
TARGET_LEAF_COUNT = 18
MIN_LEAVES = 15
MAX_LEAVES = 24
MIN_PER_PATTERN = 2
MAX_PER_FIELD = 5
MAX_PATTERN_SHARE = 0.5
MAX_CROSSLINKS_PER_NODE = 2
MAX_CROSSLINKS_TOTAL = 12


def load_interest_high_points() -> dict:
    """
    {soc_id: ["I", "C", ...]} — the real, ordered First/Second/Third
    Interest High-Points (Data/career_interest_types.csv, Element IDs
    1.B.1.g/h/i, Scale ID 'IH'), standard O*NET 1-6 RIASEC coding.
    A Data Value of 0.00 is O*NET's own "no distinct high point at
    this rank" marker and is skipped (0 isn't a valid RIASEC code).
    """
    raw = defaultdict(dict)
    with open(INTEREST_TYPES_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rank_by_name = {
            "First Interest High-Point": 1,
            "Second Interest High-Point": 2,
            "Third Interest High-Point": 3,
        }
        for row in reader:
            if row["Scale ID"] != "IH":
                continue
            rank = rank_by_name.get(row["Element Name"])
            if rank is None:
                continue
            raw[row["O*NET-SOC Code"]][rank] = float(row["Data Value"])

    result = {}
    for soc_id, ranks in raw.items():
        ordered = []
        for rank in (1, 2, 3):
            code = int(ranks.get(rank, 0.0))
            if code in RIASEC_CODE_TO_LETTER:
                ordered.append(RIASEC_CODE_TO_LETTER[code])
        result[soc_id] = ordered
    return result


def field_title(field_code: str) -> str:
    """Real official BLS SOC title at whatever granularity field_code
    actually is: 2-char major, 4-char minor, or 6-char broad (which
    uses its parent minor group's real title — BLS doesn't publish
    separate broad-group names)."""
    if len(field_code) == 2:
        return major_title(field_code)
    if len(field_code) == 4:
        return minor_title(field_code)
    return minor_title(field_code[:4])


def determine_shown_patterns(scores: dict, decisions: dict) -> list:
    """
    Level 1. Never show a trait marked "Not quite" (reject). Show
    every trait with real evidence (score >= EVIDENCE_THRESHOLD) that
    hasn't been rejected. At most one additional trait below that
    threshold is let through if explicitly marked "This fits"
    (accept) — the highest-scoring such trait, since the rule caps
    this at one regardless of how many were accepted.
    """
    strong = [
        axis for axis in AXIS_LABELS
        if scores.get(axis, 0.0) >= EVIDENCE_THRESHOLD and decisions.get(axis) != "reject"
    ]

    weak_accepted = [
        axis for axis in AXIS_LABELS
        if axis not in strong and decisions.get(axis) == "accept"
    ]
    if weak_accepted:
        weak_accepted.sort(key=lambda a: scores.get(a, 0.0), reverse=True)
        strong.append(weak_accepted[0])

    strong.sort(key=lambda a: (-scores.get(a, 0.0), list(AXIS_LABELS).index(a)))
    return strong


def assign_pattern(soc_id: str, shown_patterns: list, high_points: dict):
    """Level 3: the first of this occupation's real IH high-points
    (First, then Second, then Third) that's among the shown patterns.
    None if none match — the caller drops the occupation rather than
    force-assigning it somewhere dishonest."""
    shown_letters = {AXIS_TO_LETTER[a] for a in shown_patterns}
    for letter in high_points.get(soc_id, []):
        if letter in shown_letters:
            return LETTER_TO_AXIS[letter]
    return None


def group_into_fields(occupations: list) -> dict:
    """
    Level 2: group by real SOC minor group (first 4 chars of the
    O*NET-SOC code). A minor group with exactly one member merges up
    into its major group. Any resulting field with more than
    MAX_PER_FIELD members splits by broad group (first 6 chars); a
    broad-group split that would leave a singleton merges back into
    the ORIGINAL (pre-split) field instead of escalating further
    (approved deviation — avoids scattering a lone occupation into an
    unrelated major-level bucket).
    Returns {field_code: [occupations]}.
    """
    by_minor = defaultdict(list)
    for occ in occupations:
        by_minor[minor_group(occ["id"])].append(occ)

    fields = {}
    singleton_minors_by_major = defaultdict(list)
    for minor, occs in by_minor.items():
        if len(occs) == 1:
            singleton_minors_by_major[major_group(minor)].extend(occs)
        else:
            fields[minor] = occs
    for major, occs in singleton_minors_by_major.items():
        fields.setdefault(major, []).extend(occs)

    split_fields = {}
    for field_code, occs in fields.items():
        if len(occs) <= MAX_PER_FIELD:
            split_fields[field_code] = occs
            continue

        by_broad = defaultdict(list)
        for occ in occs:
            by_broad[broad_group(occ["id"])].append(occ)

        leftover_singletons = []
        for broad, broad_occs in by_broad.items():
            if len(broad_occs) == 1:
                leftover_singletons.extend(broad_occs)
            else:
                split_fields[broad] = broad_occs

        if leftover_singletons:
            split_fields.setdefault(field_code, []).extend(leftover_singletons)

    return split_fields


def select_occupations(scores: dict, shown_patterns: list, high_points: dict):
    """
    Ranks the real candidate pool once (existing FAISS matching
    logic, similarity kept internal/never returned to the UI), buckets
    each real candidate under its Level-3-assigned pattern, then
    greedily fills each pattern honoring: >=MIN_PER_PATTERN where real
    candidates allow it, no single field ever exceeding MAX_PER_FIELD
    (checked by actually re-running the Level-2 grouping on every
    trial addition), and no pattern exceeding MAX_PATTERN_SHARE of the
    running total. Never fabricates a candidate to hit a quota.
    """
    all_occs_by_id = {occ["id"]: occ for occ in load_career_graph()}

    # Rank the ENTIRE real dataset, not an arbitrary top-N slice: a
    # secondary shown pattern's honest matches often rank lower in
    # *overall* 6D similarity (that's dominated by the student's
    # strongest axes) even though they're a perfectly real match for
    # that specific pattern's own IH high-point. Truncating the pool
    # early was silently starving weaker-but-shown patterns of real
    # candidates that do exist further down the ranking — confirmed
    # by testing (see career-tree test run notes).
    student_vector = [scores.get(col, 0.0) for col in RIASEC_COLUMNS]
    pool_size = len(all_occs_by_id)
    ranked = match_occupations(
        student_vector, threshold=0.0,
        max_results=pool_size, min_results=pool_size,
    )

    buckets = {p: [] for p in shown_patterns}
    for m in ranked:
        pattern = assign_pattern(m["id"], shown_patterns, high_points)
        if pattern in buckets:
            occ = all_occs_by_id.get(m["id"])
            if occ:
                buckets[pattern].append(occ)

    selected_by_pattern = {p: [] for p in shown_patterns}
    cursor = {p: 0 for p in shown_patterns}

    def total_selected():
        return sum(len(v) for v in selected_by_pattern.values())

    def try_add(pattern):
        while cursor[pattern] < len(buckets[pattern]):
            candidate = buckets[pattern][cursor[pattern]]
            cursor[pattern] += 1
            trial = selected_by_pattern[pattern] + [candidate]
            if all(len(v) <= MAX_PER_FIELD for v in group_into_fields(trial).values()):
                selected_by_pattern[pattern].append(candidate)
                return True
        return False

    for pattern in shown_patterns:
        while len(selected_by_pattern[pattern]) < MIN_PER_PATTERN:
            if not try_add(pattern):
                break

    stalled = set()
    while total_selected() < TARGET_LEAF_COUNT and len(stalled) < len(shown_patterns):
        progressed = False
        for pattern in shown_patterns:
            if pattern in stalled or total_selected() >= TARGET_LEAF_COUNT:
                continue
            prospective_total = total_selected() + 1
            if len(shown_patterns) > 1 and (len(selected_by_pattern[pattern]) + 1) > MAX_PATTERN_SHARE * prospective_total:
                continue
            if try_add(pattern):
                progressed = True
            else:
                stalled.add(pattern)
        if not progressed:
            break

    all_selected = [occ for occs in selected_by_pattern.values() for occ in occs]
    return selected_by_pattern, all_selected


def compute_cross_links(all_selected: list, pattern_by_occ_id: dict, high_points: dict) -> list:
    """
    Cross-links only between occupations in DIFFERENT patterns.
    Rule 1: same real broad SOC group (first 6 chars).
    Rule 3: same real first-two IH high-points, in either order.
    (Rule 2 — task-embedding cosine similarity — deferred; no
    embeddings exist yet, approved deviation.)
    Cap MAX_CROSSLINKS_PER_NODE per node, MAX_CROSSLINKS_TOTAL total,
    keeping the strongest (both rules true beats either alone).
    """
    candidates = []
    n = len(all_selected)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = all_selected[i], all_selected[j]
            if pattern_by_occ_id[a["id"]] == pattern_by_occ_id[b["id"]]:
                continue

            rule1 = broad_group(a["id"]) == broad_group(b["id"])

            pts_a = high_points.get(a["id"], [])[:2]
            pts_b = high_points.get(b["id"], [])[:2]
            rule3 = len(pts_a) == 2 and set(pts_a) == set(pts_b)

            if not (rule1 or rule3):
                continue

            reasons = []
            if rule1:
                reasons.append(f"Both are part of {field_title(broad_group(a['id']))}.")
            if rule3:
                reasons.append(f"Both show the same top two interests ({', '.join(sorted(set(pts_a)))}).")

            candidates.append({
                "a": a["id"], "b": b["id"],
                "strength": (1 if rule1 else 0) + (1 if rule3 else 0),
                "reason": " ".join(reasons),
            })

    candidates.sort(key=lambda c: -c["strength"])

    per_node_count = defaultdict(int)
    result = []
    for c in candidates:
        if len(result) >= MAX_CROSSLINKS_TOTAL:
            break
        if per_node_count[c["a"]] >= MAX_CROSSLINKS_PER_NODE or per_node_count[c["b"]] >= MAX_CROSSLINKS_PER_NODE:
            continue
        result.append(c)
        per_node_count[c["a"]] += 1
        per_node_count[c["b"]] += 1

    return result


def build_career_tree(session_id: str) -> dict:
    """
    Returns {"nodes": [...], "edges": [...]} per the API contract —
    the full deterministic structure. Labels for field/career nodes
    are the real official/full titles as an honest placeholder; Phase
    2's AI-naming layer will shorten them (and add why/tryIt text)
    without touching which nodes or edges exist.
    """
    scores = get_latest_inference_scores(session_id)
    if not scores:
        return {"nodes": [{"id": "you", "type": "hub", "label": "You"}], "edges": []}

    decisions = get_latest_trait_decisions(session_id)
    shown_patterns = determine_shown_patterns(scores, decisions)

    if not shown_patterns:
        return {"nodes": [{"id": "you", "type": "hub", "label": "You"}], "edges": []}

    high_points = load_interest_high_points()
    selected_by_pattern, all_selected = select_occupations(scores, shown_patterns, high_points)

    # A pattern can have real Inference-score evidence yet end up
    # with zero real occupations whose own IH high-point actually
    # lands there (found in testing — a student's strongest axes
    # dominate FAISS's overall similarity ranking, so a secondary
    # pattern's honest matches can be genuinely absent, not just
    # ranked low). Showing an area node with nothing under it is a
    # dead end, not an honest reflection of "real evidence" — so a
    # pattern only becomes a shown area if real data actually backs
    # it with at least one occupation.
    shown_patterns = [p for p in shown_patterns if selected_by_pattern.get(p)]

    if not shown_patterns:
        return {"nodes": [{"id": "you", "type": "hub", "label": "You"}], "edges": []}

    pattern_by_occ_id = {
        occ["id"]: pattern
        for pattern, occs in selected_by_pattern.items()
        for occ in occs
    }

    nodes = [{"id": "you", "type": "hub", "label": "You"}]
    edges = []

    for pattern in shown_patterns:
        letter = AXIS_TO_LETTER[pattern]
        area_id = f"p:{letter}"
        nodes.append({
            "id": area_id, "type": "area", "label": AXIS_LABELS[pattern],
            "riasec": letter, "parent": "you",
        })
        edges.append({"source": "you", "target": area_id, "kind": "branch"})

        fields = group_into_fields(selected_by_pattern[pattern])
        for field_code, occs in fields.items():
            # Scoped by pattern letter: the same real SOC group can
            # legitimately hold occupations under two different
            # patterns (e.g. a "15-2" occupation whose own top IH
            # point is organizes_systems, and another "15-2"
            # occupation whose top point is investigates_why) — an
            # unscoped "f:15-2" id would collide and one field would
            # silently shadow the other in a node-id lookup.
            field_id = f"f:{letter}-{field_code}"
            title = field_title(field_code)
            nodes.append({
                "id": field_id, "type": "field",
                "label": title, "officialTitle": title,
                "parent": area_id,
            })
            edges.append({"source": area_id, "target": field_id, "kind": "branch"})

            for occ in occs:
                occ_node_id = f"o:{occ['id']}"
                sample_tasks = occ.get("sample_tasks", [])
                nodes.append({
                    "id": occ_node_id, "type": "career",
                    "label": occ["title"], "fullTitle": occ["title"],
                    "soc": occ["id"], "parent": field_id,
                    "description": occ.get("description", ""),
                    "tasks": [t["text"] for t in sample_tasks],
                    "taskIds": [t["task_id"] for t in sample_tasks],
                })
                edges.append({"source": field_id, "target": occ_node_id, "kind": "branch"})

    cross_links = compute_cross_links(all_selected, pattern_by_occ_id, high_points)
    for link in cross_links:
        edges.append({
            "source": f"o:{link['a']}", "target": f"o:{link['b']}",
            "kind": "cross", "reason": link["reason"],
        })

    return {"nodes": nodes, "edges": edges}
