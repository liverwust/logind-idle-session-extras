"""Unit-test the set arithmetic function for unhashable List objects"""


from typing import Any, Callable, List
from unittest import TestCase

import logind_idle_session_extras.list_set


class CompareListSetsTestCase(TestCase):
    """Unit-test the set arithmetic function for unhashable List objects"""

    def setUp(self):
        self._list_func = logind_idle_session_extras.list_set.compare_list_sets

    def test_identical_lists(self):
        """Two identical lists should be matched"""

        a = [1, 5, 8, 2, 4]
        b = [1, 5, 8, 2, 4]

        self.assertTrue(self._list_func(a, b))

    def test_not_quite_identical_lists(self):
        """Two similar-length lists with a missing element"""

        a = [1, 5, 7, 2, 4]
        b = [1, 5, 8, 2, 4]

        self.assertFalse(self._list_func(a, b))

    def test_identical_but_misordered_lists(self):
        """Two identical but differently-ordered lists"""

        a = [5, 1, 2, 8, 4]
        b = [1, 5, 8, 2, 4]

        self.assertTrue(self._list_func(a, b))

    def test_missing_a_element(self):
        """List A is missing an element"""

        a = [1, 5, 8, 2]
        b = [1, 5, 8, 2, 4]

        self.assertFalse(self._list_func(a, b))

    def test_missing_b_element(self):
        """List B is missing an element"""

        a = [1, 5, 8, 2, 4]
        b = [1, 5, 8, 2]

        self.assertFalse(self._list_func(a, b))

    # Shorthand for the comparison function
    _list_func: Callable[[List[Any], List[Any]], bool]
