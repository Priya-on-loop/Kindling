import unittest
import sys
import os

# Allow Python to find matching.py inside Scripts
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Scripts"))

from matching import match_occupations


class TestOccupationMatching(unittest.TestCase):

    # Sample profile 1
    def test_profile_1(self):
        student_vector = [5.0, 3.0, 4.0, 2.0, 5.0, 4.0]

        matches = match_occupations(student_vector, top_k=5)

        self.assertEqual(len(matches), 5)
        self.assertTrue(all("title" in match for match in matches))
        self.assertTrue(all("similarity" in match for match in matches))

    # Sample profile 2
    def test_profile_2(self):
        student_vector = [2.0, 5.0, 3.0, 5.0, 2.0, 4.0]

        matches = match_occupations(student_vector, top_k=5)

        self.assertEqual(len(matches), 5)
        self.assertTrue(all("title" in match for match in matches))

    # Sample profile 3
    def test_profile_3(self):
        student_vector = [4.0, 4.0, 5.0, 3.0, 2.0, 5.0]

        matches = match_occupations(student_vector, top_k=5)

        self.assertEqual(len(matches), 5)
        self.assertTrue(all("title" in match for match in matches))

    # Check that results are ranked by similarity
    def test_results_are_ranked(self):
        student_vector = [5.0, 3.0, 4.0, 2.0, 5.0, 4.0]

        matches = match_occupations(student_vector, top_k=5)

        similarities = [match["similarity"] for match in matches]

        self.assertEqual(
            similarities,
            sorted(similarities, reverse=True)
        )


if __name__ == "__main__":
    unittest.main()