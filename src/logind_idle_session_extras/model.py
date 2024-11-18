"""Abstract session model which is shared by the different components

Generally, the NamedTuple class instances defined here should be _considered_
to be immutable. Other modules should aim not to modify any state within these
objects, particularly the lists. However, there is no technical guarantee.
"""


import datetime
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


class TTY(NamedTuple):
    """Representation of the TTY assigned to a given Session"""

    # The name of the TTY/PTY (e.g., pts/3)
    name: str

    # The modification time of the TTY/PTY, which is updated by both user
    # activity and stdout/stderr from programs
    mtime: datetime.datetime

    # The access time of the TTY/PTY, which is updated only by user activity
    # (and, occasionally, by logind-idle-session-extras!)
    atime: datetime.datetime

    @property
    def full_name(self) -> str:
        """Just prepend /dev/ onto name"""
        return "/dev/" + self.name


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Textual identifier for this Session according to logind
    session_id: str

    # User identifier (UID) which owns this Session
    uid: int

    # The leader PID which is the one that registered this session
    leader_pid: int

    # The TTY or PTY which is assigned to this session (or None)
    tty: Optional[TTY]

    # The mtime of the TTY or PTY which is assigned to this session
    # (or None if tty is blank)

    # Collection of Process objects belonging to this Session
    processes: List[SessionProcess]


def find_session_with_process(search: Process,
                              sessions: List[Session]) -> Optional[Session]:
    """Attempt to locate a Session containing the given Process from a list

    This is useful when attempting to tie a backend process (e.g., Xvnc) to
    the session which contains it.
    """

    for session in sessions:
        for session_process in session.processes:
            if session_process.process == search:
                return session

    return None
