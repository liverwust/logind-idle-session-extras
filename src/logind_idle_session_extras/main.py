"""Main logic for the logind-idle-session-extras loop"""


from itertools import product
import logging
from typing import List, Mapping, NamedTuple, Optional, Union

from logind_idle_session_extras.exception import SessionParseError
import logind_idle_session_extras.getent
import logind_idle_session_extras.logind
import logind_idle_session_extras.ps
import logind_idle_session_extras.ss
import logind_idle_session_extras.tty


logger = logging.getLogger(__name__)


class SessionProcess(NamedTuple):
    """Representation of a Process specifically inside of a Session"""

    # Generic Process details for this SessionProcess
    process: logind_idle_session_extras.ps.Process

    # Whether this process has been marked as the "Leader" of its session
    # (i.e., whether Process.pid == Session.leader_pid)
    leader: bool

    # A (possibly empty) list of backend processes that this particular
    # process has tunneled back into *OR* the Sessions that they are part of
    tunnels: List[Union[logind_idle_session_extras.ps.Process, 'Session']]

    def __eq__(self, other):
        if not hasattr(other, 'process'):
            return False
        if not hasattr(other.process, 'pid'):
            return False
        return self.process.pid == other.process.pid


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Backend logind session object for this Session
    session: logind_idle_session_extras.logind.Session

    # The TTY or PTY which is assigned to this session (or None)
    tty: Optional[logind_idle_session_extras.tty.TTY]

    # The symbolic username corresponding to session.uid
    username: str

    # Collection of Process objects belonging to this Session
    processes: List[SessionProcess]

    def __eq__(self, other):
        if not hasattr(other, 'session'):
            return False
        if not hasattr(other.session, 'session_id'):
            return False
        return self.session.session_id == other.session.session_id


#def check_ssh_session_tunnel(session: Session) -> bool:
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
#

# Constructing the tree involves many local variables, necessarily
# pylint: disable-next=too-many-locals, too-many-branches
def load_sessions() -> List[Session]:
    """Construct an abstract Session/Process tree from system observations"""

    try:
        logind_sessions = logind_idle_session_extras.logind.get_all_sessions()
        loopback_connections = logind_idle_session_extras.ss.find_loopback_connections()
    except SessionParseError as err:
        logger.error('Problem while reading session and networking table '
                     'information: %s', err.message)
        return []

    resolved_usernames: Mapping[int, str] = {}

    # Constructing the tree involves many layers of nesting, necessarily
    # pylint: disable=too-many-nested-blocks
    sessions: List[Session] = []
    for logind_session in logind_sessions:
        try:
            if logind_session.uid not in resolved_usernames:
                username = logind_idle_session_extras.getent.uid_to_username(
                        logind_session.uid
                )
                resolved_usernames[logind_session.uid] = username

            session_processes: List[SessionProcess] = []
            ps_table = logind_idle_session_extras.ps.processes_in_scope_path(
                    logind_session.scope_path
            )
            for process in ps_table:
                tunnels: List[Union[logind_idle_session_extras.ps.Process,
                                    Session]] = []

                # Associate Processes thru loopback to other Processes
                for loopback_connection in loopback_connections:
                    client_processes = loopback_connection.client.processes
                    server_processes = loopback_connection.server.processes
                    for client_process in client_processes:
                        for server_process in server_processes:
                            if process == client_process:
                                if not server_process in tunnels:
                                    tunnels.append(server_process)

                session_processes.append(SessionProcess(
                        process=process,
                        leader=(process.pid == logind_session.leader),
                        tunnels=tunnels
                ))

            session_tty: Optional[logind_idle_session_extras.tty.TTY] = None
            if logind_session.tty != "":
                session_tty = logind_idle_session_extras.tty.TTY(
                        logind_session.tty
                )

            sessions.append(Session(
                    session=logind_session,
                    tty=session_tty,
                    username=resolved_usernames[logind_session.uid],
                    processes=session_processes
            ))

        except SessionParseError as err:
            logger.warning('Could not successfully parse information related '
                           'to session %s: %s',
                           logind_session.session_id,
                           err.message)

    # Go back and resolve backend tunneled Processes to their Sessions
    for session_a, session_b in product(sessions, sessions):
        for process_a, process_b in product(session_a.processes,
                                            session_b.processes):
            for index, backend_process_a in enumerate(process_a.tunnels):
                if backend_process_a == process_b.process:
                    process_a.tunnels[index] = session_b

    # Send the identified Sessions to the debug log
    logger.debug('Identified %d sessions to be reviewed:')
    for index, session in enumerate(sessions):
        tty_string = "notty"
        if session.tty is not None:
            tty_string = session.tty.name
        logger.debug('%d (id=%s): %s@%s with %d processes and '
                     '%d active tunnels',
                     index + 1,  # make index more human-friendly by adding 1
                     session.session.session_id,
                     session.username,
                     tty_string,
                     len(session.processes),
                     sum(map(lambda p: len(p.tunnels), session.processes)))

    return sessions


def apply_time_discrepancy_rule(session: Session) -> bool:
    """Check and fix a TTY whose atime is older than its mtime

    As indicated in the README, there are multiple kinds of "user activity" on
    the command-line. The systemd-logind logic for idle timeouts checks the
    atime on the TTY/PTY. User keyboard activity updates both the mtime and
    atime. On the other hand, program output _only_ updates the mtime.

    This rule ensures that the atime is touched to match the mtime, when the
    atime is older than the mtime. In doing so, program output will ALSO re-up
    the idle timeout.
    """

    if session.tty is not None:
        if session.tty.atime < session.tty.mtime:
            session.tty.touch_times(session.tty.mtime)
            return True
    return False
