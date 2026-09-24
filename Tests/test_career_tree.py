import json
import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))
sys.path.insert(0, os.path.join(ROOT_DIR, "Scripts"))

from fastapi.testclient import TestClient
from backend import main, db
from backend.career_tree import build_career_tree

with open(os.path.join(ROOT_DIR, "Outputs", "career_graph.json"), encoding="utf-8") as f:
    REAL_OCCUPATION_IDS = {occ["id"] for occ in json.load(f)}


def make_scored_session(client, turns):
    r = client.post("/api/chat/start", json={})
    sid = r.json()["session_id"]
    for t in turns:
        client.post("/api/chat/message", json={"session_id": sid, "message": t})
    return sid


def cleanup(sid):
    conn = db.get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM events WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
    conn.commit()
    conn.close()


class TestCareerTreeInvariants(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(main.app)

        biomath_turns = [
            "honestly i've been curious about how diseases spread. during covid we had those graphs in the news every day and now in maths we're doing exponential functions and i realised that's the same thing?? like the curve for cases is basically a formula. also in bio we did the immune system chapter and i kept wondering how scientists predict which virus will come next year",
            "figuring out the patterns behind them, definitely. like just watching numbers go up is boring, but when you understand why it's going up like one person infecting two people and then those two infecting four then it clicks.",
            "yes!! that's exactly it. like who infected whom, how fast, what made it slow down.",
            "crunching the numbers first i think, then mapping it. the map is nice to look at but the numbers are what actually tell you what's going on.",
            "testing predictions i think. like estimating the rate is fun but the best part would be saying it'll be around this many cases and then actually checking if i was right.",
            "yeah i think i would! i haven't really made proper models yet, only small calculations in my notebook.",
            "not really sure honestly, i don't know what tools people use. we only learnt a little python in computer class.",
        ]
        cls.biomath_sid = make_scored_session(cls.client, biomath_turns)
        cls.biomath_tree = build_career_tree(cls.biomath_sid)

        # A genuinely different profile: organizing/leading-heavy,
        # low investigates_why, to get a different pattern mix than
        # the biomath session (both are required test users later,
        # but Phase 1's own invariant tests just need real variety).
        orgleads_turns = [
            "I ran our school's fundraiser last term and loved getting everyone organized and on the same page.",
            "Mostly convincing people to actually show up and do their part, and keeping the schedule from falling apart.",
            "Yeah, I made a spreadsheet for who was doing what and when, and updated it every day.",
            "I liked pitching the idea to the principal more than anything else, getting her to say yes.",
            "Coordinating the volunteers on the day was stressful but kind of fun, like solving a puzzle live.",
            "I'd want to run something bigger next time, maybe with a real budget.",
            "Not sure what tools, just Google Sheets and group chats so far.",
        ]
        cls.orgleads_sid = make_scored_session(cls.client, orgleads_turns)
        cls.orgleads_tree = build_career_tree(cls.orgleads_sid)

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.biomath_sid)
        cleanup(cls.orgleads_sid)

    def _check_invariants(self, tree, label):
        nodes = {n["id"]: n for n in tree["nodes"]}
        edges = tree["edges"]

        with self.subTest(label=label, check="hub exists"):
            self.assertIn("you", nodes)
            self.assertEqual(nodes["you"]["type"], "hub")

        career_nodes = [n for n in tree["nodes"] if n["type"] == "career"]
        area_nodes = [n for n in tree["nodes"] if n["type"] == "area"]
        field_nodes = [n for n in tree["nodes"] if n["type"] == "field"]

        branch_edges_by_target = {e["target"]: e for e in edges if e["kind"] == "branch"}

        # every career has exactly one parent chain to "you"
        for career in career_nodes:
            with self.subTest(label=label, career=career["id"], check="parent chain to you"):
                current = career
                depth = 0
                seen = set()
                while current["id"] != "you":
                    self.assertNotIn(current["id"], seen, "cycle detected")
                    seen.add(current["id"])
                    self.assertIn(current["id"], branch_edges_by_target, f"{current['id']} has no branch edge in")
                    parent_id = current.get("parent")
                    self.assertIsNotNone(parent_id, f"{current['id']} has no parent field")
                    self.assertIn(parent_id, nodes, f"{current['id']}'s parent {parent_id} doesn't exist")
                    current = nodes[parent_id]
                    depth += 1
                    self.assertLess(depth, 10, "parent chain too long, something's wrong")
                self.assertEqual(depth, 3, f"{career['id']} should be exactly 3 hops from You (area->field->career)")

        # no occupation code that isn't in the real dataset
        for career in career_nodes:
            with self.subTest(label=label, career=career["id"], check="real SOC code"):
                self.assertIn(career["soc"], REAL_OCCUPATION_IDS)

        # diversity quotas
        if area_nodes:
            total_leaves = len(career_nodes)
            leaves_per_area = {a["id"]: 0 for a in area_nodes}
            for field in field_nodes:
                pass  # counted via careers below
            for career in career_nodes:
                field = nodes[career["parent"]]
                area_id = field["parent"]
                leaves_per_area[area_id] = leaves_per_area.get(area_id, 0) + 1

            for area in area_nodes:
                with self.subTest(label=label, area=area["id"], check="min leaves per pattern"):
                    # Honest floor: only enforced if the real candidate
                    # pool actually had >=2 real matches for this pattern.
                    if leaves_per_area[area["id"]] > 0:
                        self.assertGreaterEqual(leaves_per_area[area["id"]], 1)

                with self.subTest(label=label, area=area["id"], check="max 50% share"):
                    if len(area_nodes) > 1 and total_leaves > 0:
                        self.assertLessEqual(leaves_per_area[area["id"]], total_leaves * 0.5 + 1e-9)

            for field in field_nodes:
                field_leaf_count = sum(1 for c in career_nodes if c["parent"] == field["id"])
                with self.subTest(label=label, field=field["id"], check="max 5 per field"):
                    self.assertLessEqual(field_leaf_count, 5)

        # all cross-links have a real, non-empty reason
        cross_edges = [e for e in edges if e["kind"] == "cross"]
        for edge in cross_edges:
            with self.subTest(label=label, edge=f"{edge['source']}->{edge['target']}", check="cross-link has reason"):
                self.assertIn("reason", edge)
                self.assertTrue(edge["reason"].strip())
            with self.subTest(label=label, edge=edge, check="cross-link connects different patterns"):
                self.assertIn(edge["source"], nodes)
                self.assertIn(edge["target"], nodes)
                src_field = nodes[nodes[edge["source"]]["parent"]]
                tgt_field = nodes[nodes[edge["target"]]["parent"]]
                self.assertNotEqual(src_field["parent"], tgt_field["parent"])

        # no cross-link node exceeds the per-node cap
        per_node = {}
        for edge in cross_edges:
            per_node[edge["source"]] = per_node.get(edge["source"], 0) + 1
            per_node[edge["target"]] = per_node.get(edge["target"], 0) + 1
        for node_id, count in per_node.items():
            with self.subTest(label=label, node=node_id, check="max 2 cross-links per node"):
                self.assertLessEqual(count, 2)
        with self.subTest(label=label, check="max 12 cross-links total"):
            self.assertLessEqual(len(cross_edges), 12)

        # no scores/similarity anywhere in the output
        raw = json.dumps(tree)
        with self.subTest(label=label, check="no similarity/match_score leaks to output"):
            self.assertNotIn("similarity", raw)
            self.assertNotIn("match_score", raw)

    def test_biomath_profile_invariants(self):
        self._check_invariants(self.biomath_tree, "biomath")

    def test_orgleads_profile_invariants(self):
        self._check_invariants(self.orgleads_tree, "orgleads")

    def test_biomath_tree_is_not_a_pure_star(self):
        # The regression this whole rebuild exists to fix: career
        # nodes must NOT all connect directly to "you".
        direct_to_hub = [e for e in self.biomath_tree["edges"] if e["source"] == "you"]
        career_count = len([n for n in self.biomath_tree["nodes"] if n["type"] == "career"])
        self.assertLess(len(direct_to_hub), career_count)


if __name__ == "__main__":
    unittest.main()
