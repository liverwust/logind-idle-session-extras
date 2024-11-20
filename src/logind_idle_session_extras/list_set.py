"""Set arithmetic on an unhashable List object"""


from itertools import product, starmap
from operator import eq, truth
from typing import Any, List


def compare_list_sets(list_a: List[Any], list_b: List[Any]) -> bool:
    """Compare two "sets" which are actually just Lists of unhashable objects

    A frequent pattern throughout this project -- both in the actual
    implementation and while testing it -- is to have two "sets" of elements
    which are actually just Lists. We want to compare the two "sets" to check
    whether they are equivalent. The elements inside of the sets are
    comparable (e.g., they implement __eq__) but they are either mutable or
    otherwise not hashable, and so they cannot be thrown into a native set()
    and compared that way.

    This straightforward algorithm assumes that the lists aren't very big.
    """

    if len(list_a) != len(list_b):
        return False

    matches = len(list(filter(truth, starmap(eq, product(list_a, list_b)))))
    return matches == len(list_a)
