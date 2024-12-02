"""Main logic for the stop-idle-session loop"""


import argparse
import configparser
import datetime
from itertools import product
import logging
import logging.handlers
import re
import sys
import traceback
from typing import List, Mapping, NamedTuple, Optional, Tuple

from stop_idle_sessions.exception import SessionParseError
import stop_idle_sessions.getent
import stop_idle_sessions.logind
import stop_idle_sessions.ps
import stop_idle_sessions.ss
import stop_idle_sessions.tty
import stop_idle_sessions.x11


logger = logging.getLogger(__name__)
_DEFAULT_CONFIG_FILE = "/etc/stop-idle-sessions.conf"


class SessionProcess(NamedTuple):
    """Representation of a Process specifically inside of a Session"""

    # Generic Process details for this SessionProcess
    process: stop_idle_sessions.ps.Process

    # A (possibly empty) list of backend processes that this particular
    # process has tunneled back into
    tunneled_processes: List[stop_idle_sessions.ps.Process]

    # A (possibly empty) list of Sessions that contain the tunneled_processes
    # that this particular process has connected to
    tunneled_sessions: List['Session']

    def __eq__(self, other):
        if not hasattr(other, 'process'):
            return False
        if not hasattr(other.process, 'pid'):
            return False
        return self.process.pid == other.process.pid


class Session(NamedTuple):
    """Representation of an individual Session, combining various sources"""

    # Backend logind session object for this Session
    session: stop_idle_sessions.logind.Session

    # The TTY or PTY which is assigned to this session (or None)
    tty: Optional[stop_idle_sessions.tty.TTY]

    # The value of the DISPLAY environment variable for this particular
    # process, or None if none was assigned
    display: Optional[str]

    # The idletime (expressed as a timedelta) reported by the X11 Screen Saver
    # extension for this DISPLAY (or None if there was no DISPLAY)
    display_idle: Optional[datetime.timedelta]

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

    def __str__(self):
        return self.string_representation()

    def string_representation(self,
                              idleness: Optional[datetime.timedelta] = None) -> str:
        """Provide a string representation of the Session, maybe with idleness"""

        tty_string: str = "notty"
        if self.tty is not None:
            tty_string = self.tty.name

        nr_processes: int = len(self.processes)
        nr_tunnels: int = sum(map(lambda p: len(p.tunneled_processes),
                                  self.processes))
        nr_sessions: int = sum(map(lambda p: len(p.tunneled_sessions),
                                   self.processes))

        backend_text: str = f"w/ {nr_processes} processes"
        if nr_tunnels > 0:
            backend_text += f" hosting {nr_tunnels}"
            if nr_sessions > 0:
                backend_text += f" to {nr_sessions} backend sessions"

        idleness_text: str = ""
        if idleness is not None:
            idleness_text = f" -- idle for {idleness.total_seconds() // 60} minutes"

        return (f'session id="{self.session.session_id}" '
                f'leader={self.session.leader} '
                f'user={self.username}@{tty_string} '
                f'({backend_text}){idleness_text}')


# Constructing the tree involves many local variables, necessarily
# pylint: disable-next=too-many-locals, too-many-branches
def load_sessions() -> List[Session]:
    """Construct an abstract Session/Process tree from system observations"""

    try:
        logind_sessions = stop_idle_sessions.logind.get_all_sessions()
        loopback_connections = stop_idle_sessions.ss.find_loopback_connections()
    except SessionParseError as err:
        logger.error('Problem while reading session and networking table '
                     'information: %s', err.message)
        raise err

    resolved_usernames: Mapping[int, str] = {}

    # Constructing the tree involves many layers of nesting, necessarily
    # pylint: disable=too-many-nested-blocks
    sessions: List[Session] = []
    for logind_session in logind_sessions:
        try:
            display_info = stop_idle_sessions.x11.X11SessionProcesses()

            if logind_session.uid not in resolved_usernames:
                username = stop_idle_sessions.getent.uid_to_username(
                        logind_session.uid
                )
                resolved_usernames[logind_session.uid] = username

            session_processes: List[SessionProcess] = []
            ps_table = stop_idle_sessions.ps.processes_in_scope_path(
                    logind_session.scope_path
            )
            for process in ps_table:
                tunneled_processes: List[stop_idle_sessions.ps.Process] = []
                display_info.add(process)

                # Associate Processes thru loopback to other Processes
                for loopback_connection in loopback_connections:
                    client_processes = loopback_connection.client.processes
                    server_processes = loopback_connection.server.processes
                    for client_process in client_processes:
                        for server_process in server_processes:
                            if process == client_process:
                                if not server_process in tunneled_processes:
                                    tunneled_processes.append(server_process)

                session_processes.append(SessionProcess(
                        process=process,
                        tunneled_processes=tunneled_processes,
                        tunneled_sessions=[]
                ))

            session_tty: Optional[stop_idle_sessions.tty.TTY] = None
            # If a session is "lingering" (i.e., has no remaining Leader
            # process), then we cannot and do not trust its tty string.
            if logind_session.tty != "" and logind_session.leader != 0:
                session_tty = stop_idle_sessions.tty.TTY(
                        logind_session.tty
                )

            display_result = display_info.retrieve_least_display_idletime()

            if display_result is not None:
                sessions.append(Session(
                        session=logind_session,
                        tty=session_tty,
                        display=display_result[0],
                        display_idle=display_result[1],
                        username=resolved_usernames[logind_session.uid],
                        processes=session_processes
                ))
            else:
                sessions.append(Session(
                        session=logind_session,
                        tty=session_tty,
                        display=None,
                        display_idle=None,
                        username=resolved_usernames[logind_session.uid],
                        processes=session_processes
                ))

        except SessionParseError as err:
            logger.warning('Could not successfully parse information related '
                           'to session id="%s": %s',
                           logind_session.session_id,
                           err.message)
            traceback.print_exc(file=sys.stderr)

    # Go back and resolve backend tunneled Processes to their Sessions
    for session_a, session_b in product(sessions, sessions):
        for process_a, process_b in product(session_a.processes,
                                            session_b.processes):
            for backend_process_a in process_a.tunneled_processes:
                if backend_process_a == process_b.process:
                    process_a.tunneled_sessions.append(session_b)

    return sessions


def skip_ineligible_session(session: Session,
                            excluded_users: Optional[List[str]] = None) -> Tuple[bool,
                                                                                 str]:
    """Check whether a session is ineligible for idleness timeout enforcement

    Returns True if this session meets any of the criteria for being
    "ineligible" (see README.md) and should not be processed further. If
    False, then the caller should continue processing.

    The returned string is a short descriptor for why the session was skipped.
    It is blank if the session was not skipped.
    """

    # Graphical sessions should be protected by screensavers, not idle
    # timeouts. (_Tunneled_ graphical sessions are a different story -- see
    # README.md for details.)
    # https://github.com/systemd/systemd/blob/v256.8/src/login/logind-session.c#L1650
    if session.session.session_type in ('x11', 'wayland', 'mir'):
        return True, 'graphical'

    # systemd-logind sessions without an assigned teletype (TTY/PTY) which
    # represent "noninteractive" sessions.
    if session.tty is None:
        return True, 'noninteractive'

    # systemd-logind sessions belonging to one of the "excluded_users" in the
    # provided list (if any).
    if excluded_users is not None and session.username in excluded_users:
        return True, f'excluded user ({session.username})'

    # systemd-logind session whose Scope Leader has been terminated. See
    # README.md for a discussion of why this is relevant.
    if session.session.leader == 0:
        return True, 'lingering'

    return False, ''


def compute_idleness_metric(session: Session,
                            now: datetime.datetime,
                            nested: bool = False) -> datetime.timedelta:
    """Determine the most "optimistic" idleness metric for the given Session

    By drawing from all of the potential sources of idleness/activity, find
    the one which gives the user the most opportunity to keep their session
    alive. For example, if the user's keystroke activity would indicate 10
    minutes of idleness, but their tunneled VNC session experienced activity
    in the past 5 minutes, then the overall idleness should only be reported
    as 5 minutes.

    Some data sources (e.g., a TTY's atime) provide an absolute timestamp
    instead of a timedelta. The caller is expected to supply the current
    timestamp (e.g., datetime.datetime.now() OR a fake value for testing) so
    that such timestamps may be converted into a timedelta.

    Idleness can involve the participation of a tunneled session. This
    analysis should never need to extend past "depth two" -- e.g., the
    idleness of an SSH session which has tunneled through to a VNC session may
    depend on the idleness of the VNC session. _However_, we never need to
    (and don't want to!) enter a recursive loop where a session relates to
    itself, or two sessions relate circularly. As a protection against this,
    the nested argument will keep this function from analyzing further Session
    entries after the first one.
    """

    minimum_idle: Optional[datetime.timedelta] = None
    determined_by: str = ""

    # The atime on a TTY for a terminal session is touched whenever the user
    # enters keyboard input.
    if (session.tty is not None and (minimum_idle is None or
                                     now - session.tty.atime < minimum_idle)):
        minimum_idle = now - session.tty.atime
        determined_by = f"atime on {session.tty.name}"

    # The mtime on a TTY for a terminal session is touched whenever the user
    # enters keyboard input (same as atime) *OR* whenever a program generates
    # standard output/error onto the screen.
    if (session.tty is not None and (minimum_idle is None or
                                     now - session.tty.mtime < minimum_idle)):
        minimum_idle = now - session.tty.mtime
        determined_by = f"mtime on {session.tty.name}"

    # The idleness of a session which contains running some running X11 server
    # (probably Xwayland or Xorg or Xvnc) can be influenced by the same
    # activity metric tracked by the X11 Screen Saver extension.
    if (session.display_idle is not None and (minimum_idle is None or
                                              session.display_idle < minimum_idle)):
        minimum_idle = session.display_idle
        determined_by = f"X11 idleness on DISPLAY={session.display}"

    # The idleness of a session which has tunneled into another session
    # (primarily VNC over SSH) can be influenced by the tunneled session.
    # However, as explained in the docstring, this must be guarded against
    # recursive loops by enforcing a maximum depth of 2 (i.e., the outer
    # session and the inner session).
    if not nested:
        for session_process in session.processes:
            for tunneled_session in session_process.tunneled_sessions:
                # Do NOT check the inner session for "eligibility"
                try:
                    inner_idle = compute_idleness_metric(tunneled_session,
                                                        now,
                                                        nested=True)
                    if minimum_idle is None or inner_idle < minimum_idle:
                        minimum_idle = inner_idle
                        determined_by = ("idleness of nested session " +
                                            tunneled_session.session.session_id)
                except SessionParseError:
                    # Just skip this attempt if it didn't work out
                    pass

    if minimum_idle is None:
        raise SessionParseError('Could not identify an idle duration for ' +
                                session.session.session_id)

    logger.debug("Computed idleness for %s (based on %s)",
                 session.string_representation(minimum_idle),
                 determined_by)

    return minimum_idle


# This is a bit complicated, but it's the glue for everything else.
# pylint: disable-next=too-many-branches, too-many-locals, too-many-statements
def main():
    """Overall main loop routine for this application"""
    parser = argparse.ArgumentParser(
            prog='stop_idle_sessions.main',
            description=("Stop idle `systemd-logind` sessions to prevent "
                         "interactive access from unattended terminals. "
                         "E.g., a laptop left unlocked in a coffee shop, "
                         "with an SSH session into an internal network "
                         "resource.")
    )
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help=("Don't actually take any actions, but just log "
                              "(to stdout, not syslog) what would have "
                              "happened"))
    parser.add_argument('-s', '--syslog', action='store_true',
                        help=("Write logged messages (including debug logs, "
                              "if configured) to syslog instead of stdout. "))
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Increase verbosity to incorporate debug logs "
                             "(either to stdout during dry-run, or syslog "
                             "normally)")
    parser.add_argument('-c', '--config-file', action='store',
                        default=_DEFAULT_CONFIG_FILE,
                        help="Override the location of the configuration INI "
                             "format file")

    args = parser.parse_args()

    config = configparser.ConfigParser()
    config['stop-idle-sessions'] = {
            'dry-run': 'no',
            'syslog': 'no',
            'verbose': 'no',
            'excluded-users': '',
            'timeout': '15'
    }

    try:
        with open(args.config_file, "r", encoding='utf-8') as config_f:
            config.read_file(config_f, source=args.config_file)
    except OSError as err:
        # If it was the default file that failed to open, then just ignore the
        # failure. Otherwise, this is a fatal condition.
        if args.config_file != _DEFAULT_CONFIG_FILE:
            logger.error('Problem while reading a custom config file '
                         'located at %s: %s',
                         args.config_file,
                         str(err))
            raise err

    try:
        dry_run: bool = config.getboolean('stop-idle-sessions', 'dry-run')
        syslog: bool = config.getboolean('stop-idle-sessions', 'syslog')
        verbose: bool = config.getboolean('stop-idle-sessions', 'verbose')
        excluded_users: List[str] = list(map(lambda x: x.strip(),
                                             re.split(r'[,;:]',
                                                      config.get('stop-idle-sessions',
                                                                 'excluded-users'))))
        timeout: int = config.getint('stop-idle-sessions', 'timeout')
    except ValueError as err:
        logger.error('Problem while parsing arguments: %s',
                     str(err))
        raise err

    # Command-line argument can override the config bools
    if args.dry_run:
        dry_run = True
    if args.syslog:
        syslog = True
    if args.verbose:
        verbose = True

    if syslog:
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        handler.ident = 'stop-idle-sessions '
        logger.addHandler(handler)
    else:
        logger.addHandler(logging.StreamHandler())

    if verbose:
        logger.setLevel(logging.DEBUG)

    now = datetime.datetime.now()
    sessions = load_sessions()
    for session in sessions:
        skip_session, why = skip_ineligible_session(session, excluded_users)

        try:
            idletime = compute_idleness_metric(session, now)

            if idletime >= datetime.timedelta(seconds=60 * timeout):
                if skip_session:
                    logger.debug('Skipping %s session %s',
                                 why,
                                 session.string_representation(idletime))
                elif dry_run:
                    logger.warning('Not terminating (dry run) %s',
                                   session.string_representation(idletime))
                else:
                    logger.warning('Terminating (dry run) %s',
                                   session.string_representation(idletime))
                    session.session.kill_session_leader()

        except SessionParseError as err:
            logger.debug('Could not determine idletime for %s (%s)',
                         session.string_representation(),
                         err.message)
            if not skip_session:
                raise err


if __name__ == "__main__":
    main()
