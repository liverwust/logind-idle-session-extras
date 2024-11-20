"""Main logic for the logind-idle-session-extras loop"""


from itertools import product
from typing import List, NamedTuple, Optional, Union

from . import logind, ps, ss, tty


class SessionProcess(NamedTuple):
    """Representation of a Process specifically inside of a Session"""

    # Generic Process details for this SessionProcess
    process: ps.Process

    # Whether this process has been marked as the "Leader" of its session
    # (i.e., whether Process.pid == Session.leader_pid)
    leader: bool

    # A (possibly empty) list of backend processes that this particular
    # process has tunneled back into *OR* the Sessions that they are part of
    tunnels: List[Union[ps.Process, 'Session']]


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Backend logind session object for this Session
    session: logind.Session

    # The TTY or PTY which is assigned to this session (or None)
    tty: Optional[tty.TTY]

    # Collection of Process objects belonging to this Session
    processes: List[SessionProcess]

    def terminate(self):
        """Terminate the backend logind session and its processes"""
        self.session.terminate()


#def _check_time_discrepancy(session: Session) -> bool:
#    """Check whether the TTY's atime is at least as new as the mtime
#
#    As indicated in the README, there are multiple kinds of "user activity" on
#    the command-line. The systemd-logind logic for idle timeouts checks the
#    atime on the TTY/PTY. User keyboard activity updates both the mtime and
#    atime. On the other hand, program output _only_ updates the mtime.
#
#    This rule ensures that the atime is touched to match the mtime, when the
#    atime is older than the mtime. In doing so, program output will ALSO re-up
#    the idle timeout.
#    """
#
#    if session.tty is not None:
#        if session.tty.atime < session.tty.mtime:
#            return True
#    return False
#
#
#def _check_ssh_session_tunnel(session: Session) -> bool:
#    """Check whether an SSH session is tunneled to a backend session
#
#    This would be something like `ssh -L 5901:localhost:5901 <host>`. The Rule
#    will detect a tunnel only so long as it is actually part of an active
#    connection. A user needs to be connected to the client-side (and the
#    server-side needs to have relayed that connection) in order for this to
#    trigger. Simply _specifying_ that a tunnel should exists (-L) is not
#    enough.
#    """
#
#    for session_processes in session.processes:
#        for tunnel_backend in session_processes.tunnels:
#            if isinstance(tunnel_backend, Session):
#                pass


def load_sessions() -> List[Session]:
    """Construct an abstract Session/Process tree from system observations"""

    logind_manager = logind.Manager()
    logind_sessions = logind_manager.get_all_sessions()
    loopback_connections = ss.find_loopback_connections()

    sessions: List[Session] = []
    for logind_session in logind_sessions:
        session_processes: List[SessionProcess] = []
        for process in ps.processes_in_scope_path(logind_session.scope_path):
            tunnels: List[Union[ps.Process, Session]] = []

            # Associate Processes thru loopback connections to other Processes
            for loopback_connection in loopback_connections:
                for client_process in loopback_connection.client.processes:
                    for server_process in loopback_connection.server.processes:
                        if process == client_process:
                            if not server_process in tunnels:
                                tunnels.append(server_process)

            session_processes.append(SessionProcess(
                    process=process,
                    leader=(process.pid == logind_session.leader),
                    tunnels=tunnels
            ))

        session_tty: Optional[tty.TTY] = None
        if logind_session.tty != "":
            session_tty = tty.TTY(logind_session.tty)

        sessions.append(Session(
                session=logind_session,
                tty=session_tty,
                processes=session_processes
        ))

    # Go back and resolve backend tunneled Processes to their Sessions
    for sessionA, sessionB in product(sessions, sessions):
        for processA, processB in product(sessionA.processes,
                                          sessionB.processes):
            for index, backend_processA in enumerate(processA.tunnels):
                if backend_processA == processB:
                    processA.tunnels[index] = sessionB

    return sessions
