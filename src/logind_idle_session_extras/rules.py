"""Abstract sessions, along with pattern-matching rules"""


import json
import re
from typing import Collection, NamedTuple, Optional, Tuple


class Process(NamedTuple):
    """Representation of a process running within an individual Session"""

    # Process identifier (PID) of this process
    pid: int

    # Short name of the binary image (e.g., "sshd") for this process
    comm: str

    # Whether this process has been marked as the "Leader" of its session
    # (i.e., whether Process.pid == Session.leader_pid)
    leader: bool

    # The full command line that the process is running with
    cmdline: str

    # A (possibly empty) list of (PID, port#) pairs representing local server
    # processes (Xvnc) that this particular process has connected with
    tunnels: Collection[Tuple[int, int]]


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Textual identifier for this Session according to logind
    session_id: str

    # User identifier (UID) which owns this Session
    uid: int

    # Symbolic username which owns this session, corresponding to uid
    username: str

    # The TTY or PTY which is assigned to this session
    tty: str

    # Collection of Process objects belonging to this Session
    processes: Collection[Process]


class Rule:
    """Match rules to identify a Session->Process entry for further action

    A Rule gives one or more conditions -- all of which must be met -- which
    are run against each Session->Process entry. If a Rule matches a
    Session->Process, then the Session should be "touched" in some way.

    If any field is left as None, then it will not participate in the match
    (i.e., the corresponding Session or Process field will be ignored).
    """

    # Fixed-string match against the symbolic username owner of the Session
    username: Optional[str]

    # Regular expression match (not search) against the cmdline of the Process
    cmdline_re: Optional[str]

    # Fixed-string match against the short process name of a tunneled server
    tunnel_comm: Optional[str]

    def __init__(self, username=None, cmdline_re=None, tunnel_comm=None):
        self.username = username
        self.cmdline_re = cmdline_re
        self.tunnel_comm = tunnel_comm

    def match(self, session: Session) -> bool:
        """Returns true if the Session matches this Rule false if not"""

        if self.username is not None:
            if session.username != self.username:
                return False

        if self.cmdline_re is not None:
            for process in session.processes:
                if re.match(self.cmdline_re, process.cmdline) is None:
                    return False

        if self.tunnel_comm is not None:
            for process in session.processes:
                if process.comm != self.tunnel_comm:
                    return False

        return True

    def filter(self, sessions: Collection[Session]) -> Collection[Session]:
        """Return the Sessions which match this Rule from the collection"""

        return filter(lambda x: self.match(x), sessions)


def parse_rules_from_json(fp) -> Collection[Rule]:
    """Deserialize JSON into Rules from the given file-like object fp"""

    return json.load(fp, object_hook=Rule)
