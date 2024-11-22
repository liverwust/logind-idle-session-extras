"""Unit-test the set arithmetic function for unhashable List objects"""


from unittest import TestCase

from stop_idle_sessions import list_set


class CompareListSetsTestCase(TestCase):
    """Unit-test the set arithmetic function for unhashable List objects"""

    def test_identical_lists(self):
        """Two identical lists should be matched"""

        list_a = [1, 5, 8, 2, 4]
        list_b = [1, 5, 8, 2, 4]

        matchup = list_set.matchup_list_sets(list_a, list_b)
        similar = list_set.compare_list_sets(list_a, list_b)

        self.assertListEqual(sorted(matchup, key=lambda x: x[0]),
                             [(1, 1),
                              (2, 2),
                              (4, 4),
                              (5, 5),
                              (8, 8)])
        self.assertTrue(similar)

    def test_not_quite_identical_lists(self):
        """Two similar-length lists with a missing element"""

        list_a = [1, 5, 7, 2, 4]
        list_b = [1, 5, 8, 2, 4]

        matchup = list_set.matchup_list_sets(list_a, list_b)
        similar = list_set.compare_list_sets(list_a, list_b)

        self.assertListEqual(sorted(matchup, key=lambda x: x[0]),
                             [(1, 1),
                              (2, 2),
                              (4, 4),
                              (5, 5)])
        self.assertFalse(similar)

    def test_identical_but_misordered_lists(self):
        """Two identical but differently-ordered lists"""

        list_a = [5, 1, 2, 8, 4]
        list_b = [1, 5, 8, 2, 4]

        matchup = list_set.matchup_list_sets(list_a, list_b)
        similar = list_set.compare_list_sets(list_a, list_b)

        self.assertListEqual(sorted(matchup, key=lambda x: x[0]),
                             [(1, 1),
                              (2, 2),
                              (4, 4),
                              (5, 5),
                              (8, 8)])
        self.assertTrue(similar)

    def test_missing_a_element(self):
        """List A is missing an element"""

        list_a = [1, 5, 8, 2]
        list_b = [1, 5, 8, 2, 4]

        matchup = list_set.matchup_list_sets(list_a, list_b)
        similar = list_set.compare_list_sets(list_a, list_b)

        self.assertListEqual(sorted(matchup, key=lambda x: x[0]),
                             [(1, 1),
                              (2, 2),
                              (5, 5),
                              (8, 8)])
        self.assertFalse(similar)

    def test_missing_b_element(self):
        """List B is missing an element"""

        list_a = [1, 5, 8, 2, 4]
        list_b = [1, 5, 8, 2]

        matchup = list_set.matchup_list_sets(list_a, list_b)
        similar = list_set.compare_list_sets(list_a, list_b)

        self.assertListEqual(sorted(matchup, key=lambda x: x[0]),
                             [(1, 1),
                              (2, 2),
                              (5, 5),
                              (8, 8)])
        self.assertFalse(similar)
