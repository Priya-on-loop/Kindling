"""
Resolves a Reflection note's plain-language LLM extraction (see
ai_core/reflection_extract.py) against a student's REAL current
Career Graph tree, and applies/undoes the one kind of preference
(patternAdjustments) that changes something outside the reflection_
preferences table itself (a session's live Inference score).

hideFields/focusField are deliberately NOT "applied" here in the
sense of writing a mutation somewhere - they're just resolved to a
real node's real SOC id/field-code and stored as a preference row;
career_tree.py reads that table fresh on every tree build (see
_load_reflection_shaping), so nothing here needs an "apply" step for
those two, and nothing needs a separate "undo" step either - deleting
the row (backend/db.py) is the undo.
"""

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.append(str(BACKEND_DIR))

from soc_titles import minor_group, major_group, broad_group
from db import get_latest_inference_scores, log_event

# Same real axis<->label mapping career_tree.py and frontend/js/
# patterns.js both already use - not re-invented here.
LABEL_TO_TRAIT = {
    "Build & tinker": "builds_tinkers",
    "Investigates why": "investigates_why",
    "Create & express": "creates_expresses",
    "Works with people": "works_with_people",
    "Organizes systems": "organizes_systems",
    "Leads & persuades": "leads_persuades",
}


STOPWORDS = {"and", "the", "of", "for", "in", "a", "an", "to", "with", "or"}
STEM_LEN = 6


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _tokens(s: str) -> set:
    return set(_normalize(s).split())


def _stem(tok: str) -> str:
    """Crude common-prefix stemming so 'finance' still matches
    'Financial' and 'health' still matches 'Healthcare' - a plain
    token-equality check misses both (neither is a substring of the
    other), and this is a real-world student wording problem, not an
    edge case: the whole point of resolving against real SOC/O*NET
    titles is that students describe fields in everyday words, not
    official classification language."""
    return tok[:STEM_LEN] if len(tok) >= 5 else tok


def _meaningful_tokens(s: str) -> set:
    return {t for t in _tokens(s) if len(t) >= 3 and t not in STOPWORDS}


def resolve_against_tree(text: str, tree: dict, node_types=("field", "career")):
    """
    Best-matching real node in `tree` for a plain-language phrase the
    student wrote, or None if nothing real matches well enough.
    Checked against both the node's current (possibly AI-shortened)
    display label and its real official/full O*NET or SOC title, so
    a mention resolves whether the student used the on-screen name or
    a more generic word for it (e.g. "finance" against a field whose
    real BLS title is "Financial Specialists").
    """
    text_norm = _normalize(text)
    if not text_norm:
        return None
    text_tokens = _meaningful_tokens(text)
    text_stems = {_stem(t): t for t in text_tokens}

    best_node, best_score = None, 0.0
    for node in tree.get("nodes", []):
        if node.get("type") not in node_types:
            continue
        for cand in (node.get("label", ""), node.get("officialTitle") or node.get("fullTitle") or ""):
            cand_norm = _normalize(cand)
            if not cand_norm:
                continue
            if text_norm == cand_norm:
                score = 1.0
            elif text_norm in cand_norm or cand_norm in text_norm:
                score = 0.85
            else:
                cand_stems = {_stem(t) for t in _meaningful_tokens(cand)}
                shared = set(text_stems) & cand_stems
                if not shared:
                    score = 0.0
                else:
                    ratio = len(shared) / max(len(text_stems), 1)
                    # A single shared SPECIFIC word (e.g. "health",
                    # "insurance") is real signal on its own in this
                    # small-vocabulary domain, even if other words in
                    # the phrase ("public", "really") don't map to
                    # anything in an official title.
                    has_strong_match = any(len(text_stems[s]) >= 6 for s in shared)
                    score = max(0.55 * ratio, 0.6 if has_strong_match else 0.0)
            if score > best_score:
                best_score, best_node = score, node

    return best_node if best_score >= 0.5 else None


def field_code_of(node: dict) -> str | None:
    """'f:C-15-2' -> '15-2' (letter is always exactly 1 char right
    after 'f:', then exactly one dash, then the real SOC field code -
    see career_tree.py's field_id construction)."""
    node_id = node.get("id", "")
    if not node_id.startswith("f:"):
        return None
    return node_id[4:]


def resolve_hide_field(text: str, tree: dict) -> dict | None:
    """Real node (field or career) this hide-mention resolves to, as
    a {label, extra} pair ready for db.add_reflection_preference -
    or None if nothing in the student's real current tree matches."""
    node = resolve_against_tree(text, tree, node_types=("field", "career"))
    if node is None:
        return None
    if node["type"] == "career":
        return {"label": node["label"], "extra": {"node_type": "career", "soc": node["soc"]}}
    field_code = field_code_of(node)
    if not field_code:
        return None
    return {"label": node["label"], "extra": {"node_type": "field", "field_code": field_code}}


def resolve_focus_field(text: str, go_deeper: bool, tree: dict) -> dict | None:
    node = resolve_against_tree(text, tree, node_types=("field",))
    if node is None:
        return None
    field_code = field_code_of(node)
    if not field_code:
        return None
    return {"label": node["label"], "extra": {"field_code": field_code, "go_deeper": bool(go_deeper)}}


def resolve_new_to_them(text: str, tree: dict) -> dict:
    """Purely a display chip (see ai_core/reflection_extract.py's
    docstring - it's not in the apply list), so unlike the two
    resolvers above this never returns None: an unmatched mention
    still becomes a chip, just with the student's own wording instead
    of a resolved node label."""
    node = resolve_against_tree(text, tree, node_types=("career", "field"))
    if node is not None:
        return {"label": node["label"], "extra": {"node_type": node["type"], "soc": node.get("soc")}}
    return {"label": text.strip(), "extra": None}


def apply_pattern_adjustment(session_id: str, pattern_label: str, note: str) -> dict | None:
    """
    Same mechanism POST /api/user/trait/decision's 'reject' action
    already uses: overwrite this one trait to 0.0 in a fresh
    profile_updated event carrying the full current 6-dim vector,
    which becomes the new 'latest' score everywhere (Inference,
    Career Graph). Returns {trait, from_value} for the preference
    row's `extra` (so undo_pattern_adjustment can restore exactly
    this one trait later) - or None if there's no live score to
    adjust yet.
    """
    trait = LABEL_TO_TRAIT.get(pattern_label)
    if trait is None:
        return None

    scores = get_latest_inference_scores(session_id)
    if not scores:
        return None

    clean_scores = {k: float(v) for k, v in scores.items() if k in LABEL_TO_TRAIT.values()}
    from_value = clean_scores.get(trait, 0.0)

    clean_scores[trait] = 0.0
    log_event(session_id, "trait_rejected", {"trait": trait, "new_score": 0.0, "source": "reflection_note", "note": note})
    log_event(session_id, "profile_updated", clean_scores)

    return {"trait": trait, "session_id": session_id, "from_value": from_value, "to_value": 0.0}


def undo_pattern_adjustment(extra: dict) -> bool:
    """
    Restores exactly the one trait a pattern-adjust preference
    changed, back to what it was immediately before that adjustment -
    without disturbing any OTHER trait's current live value (read
    fresh at undo time, not the stale snapshot from when the
    adjustment was first applied).
    """
    if not extra or "trait" not in extra or "session_id" not in extra:
        return False

    session_id = extra["session_id"]
    trait = extra["trait"]
    from_value = extra.get("from_value", 0.0)

    scores = get_latest_inference_scores(session_id)
    if not scores:
        return False

    clean_scores = {k: float(v) for k, v in scores.items() if k in LABEL_TO_TRAIT.values()}
    clean_scores[trait] = float(from_value)

    log_event(session_id, "profile_updated", clean_scores)
    log_event(session_id, "reflection_pattern_undo", {"trait": trait, "restored_to": from_value})
    return True
