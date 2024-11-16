"""Abstract sessions, along with pattern-matching rules"""


import json
import re
from typing import List, NamedTuple, Optional


class Process(NamedTuple):
    """Representation of a process either inside of a Session or otherwise"""

    # Process identifier (PID) of this process
    pid: int

    # Short name of the binary image (e.g., "sshd") for this process
    comm: str

    # The full command line that the process is running with
    cmdline: str


class SessionProcess(NamedTuple):
    """Representation of a Process specifically inside of a Session"""

    # Generic Process details for this SessionProcess
    process: Process

    # Whether this process has been marked as the "Leader" of its session
    # (i.e., whether Process.pid == Session.leader_pid)
    leader: bool

    # A (possibly empty) list of backend processes that this particular
    # process has tunneled back into
    tunnels: List[Process]


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Textual identifier for this Session according to logind
    session_id: str

    # User identifier (UID) which owns this Session
    uid: int

    # The leader PID which is the one that registered this session
    leader_pid: int

    # The TTY or PTY which is assigned to this session (or a blank string)
    tty: str

    # Collection of Process objects belonging to this Session
    processes: List[SessionProcess]


class Rule:
    """Match rules to identify a Session->Process entry for further action

    A Rule gives one or more conditions -- all of which must be met -- which
    are run against each Session->Process entry. If a Rule matches a
    Session->Process, then the Session should be "touched" in some way.

    If any field is left as None, then it will not participate in the match
    (i.e., the corresponding Session or Process field will be ignored).
    """

    # Fixed-string match against the numeric UID owner of the Session
    uid: Optional[int]

    # Regular expression match (not search) against the cmdline of the Process
    cmdline_re: Optional[str]

    # Fixed-string match against the short process name of a tunneled server
    tunnel_comm: Optional[str]

    def __init__(self, uid=None, cmdline_re=None, tunnel_comm=None):
        self.uid = uid
        self.cmdline_re = cmdline_re
        self.tunnel_comm = tunnel_comm

    def match(self, session: Session) -> bool:
        """Returns true if the Session matches this Rule false if not"""

        if self.uid is not None:
            if session.uid != self.uid:
                return False

        if self.cmdline_re is not None:
            found = False
            for process in map(lambda p: p.process,
                               session.processes):
                if re.match(self.cmdline_re, process.cmdline) is not None:
                    found = True
            if not found:
                return False

        if self.tunnel_comm is not None:
            found = False
            for process in session.processes:
                for tunnel in process.tunnels:
                    if tunnel.comm != self.tunnel_comm:
                        found = True
            if not found:
                return False

        return True

    def filter(self, sessions: List[Session]) -> List[Session]:
        """Return the Sessions which match this Rule from the collection"""

        return list(filter(lambda x: self.match(x), sessions))


def parse_rules_from_json(fp) -> List[Rule]:
    """Deserialize JSON into Rules from the given file-like object fp"""

    return json.load(fp, object_hook=Rule)
