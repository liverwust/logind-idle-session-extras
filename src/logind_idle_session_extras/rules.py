"""Rules for acting on the abstract session model"""


import abc
import re
from typing import List, Optional

from logind_idle_session_extras import model


class Rule(abc.ABC):
    """Match rules to identify a Session->Process entry for further action

    A Rule gives one or more conditions -- all of which must be met -- which
    are run against each Session->Process entry. If a Rule matches a
    Session->Process, then the action is taken against that Session.
    """

    @abc.abstractmethod
    def match(self, session: model.Session) -> bool:
        """Returns true if the Session matches this Rule false if not"""
        pass

    def filter(self,
               sessions: List[model.Session]) -> List[model.Session]:
        """Return the Sessions which match this Rule from the collection"""
        return list(filter(lambda x: self.match(x), sessions))


class 
