import unittest

from backend.shap_explainer import explain_match


class TestSHAPExplainer(unittest.TestCase):

    def setUp(self):
        self.student_vector = [
            4.6,
            3.4,
            3.6,
            2.0,
            5.0,
            3.6
        ]

        self.occupation_id = "11-1011.00"

    def test_explain_match_returns_occupation(self):
        result = explain_match(
            self.student_vector,
            self.occupation_id
        )

        self.assertEqual(
            result["occupation_id"],
            self.occupation_id
        )

        self.assertEqual(
            result["occupation"],
            "Chief Executives"
        )

    def test_similarity_is_returned(self):
        result = explain_match(
            self.student_vector,
            self.occupation_id
        )

        self.assertIsInstance(
            result["similarity"],
            float
        )

    def test_six_contributions_are_returned(self):
        result = explain_match(
            self.student_vector,
            self.occupation_id
        )

        contributions = result["contributions"]

        self.assertEqual(len(contributions), 6)

        expected_dimensions = {
            "creates_expresses",
            "organizes_systems",
            "investigates_why",
            "builds_tinkers",
            "works_with_people",
            "leads_persuades"
        }

        self.assertEqual(
            set(contributions.keys()),
            expected_dimensions
        )

    def test_contributions_are_numbers(self):
        result = explain_match(
            self.student_vector,
            self.occupation_id
        )

        for value in result["contributions"].values():
            self.assertIsInstance(value, float)


if __name__ == "__main__":
    unittest.main()