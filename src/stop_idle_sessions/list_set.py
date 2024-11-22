"""Set arithmetic on an unhashable List object"""


from itertools import product
from typing import Any, List, Tuple


def matchup_list_sets(list_a: List[Any],
                      list_b: List[Any]) -> List[Tuple[Any, Any]]:
    """Extract matches from two "sets" which are actually unhashable Lists

    A frequent pattern throughout this project -- both in the actual
    implementation and while testing it -- is to have two "sets" of elements
    which are actually just Lists. We want to compare the two "sets" and look
    for elements which are equivalent (according to __eq__). Normally this
    could be done with the set() type, but not for unhashable or mutable
    objects.

    Similar to the zip() function, this will return tuples of items from
    list_a and list_b. Not all elements will necessarily be represented --
    only those elements which have an equivalent match in the other list.

    This straightforward algorithm assumes that the lists aren't very big.
    """

    cartesian = product(list_a, list_b)
    matches = filter(lambda x: x[0] == x[1], cartesian)
    return list(matches)

def compare_list_sets(list_a: List[Any], list_b: List[Any]) -> bool:
    """Compare two "sets" which are actually just Lists of unhashable objects

    This is a further convenience around matchup_list_sets which simply
    returns True if the lists are equivalent (in the manner described for
    matchup_list_sets), or False otherwise.
    """

    if len(list_a) != len(list_b):
        return False
    return len(matchup_list_sets(list_a, list_b)) == len(list_a)
