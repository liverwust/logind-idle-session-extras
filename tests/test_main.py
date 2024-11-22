"""Common logic for the main loop, shared across all scenarios"""


import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Callable, List, Mapping, Optional, Set, Union, Tuple
from unittest import TestCase, TestSuite
from unittest.mock import Mock, patch

from stop_idle_sessions.list_set import matchup_list_sets
import stop_idle_sessions.main


class MainLoopTestCase(TestCase):
    """Unit testing for the main module

    This TestCase is meant to be subclassed, NOT run directly. The load_tests
    function at the bottom of this module prevents it from being
    auto-discovered.
    """

    #
    # Subclasses need to override these methods
    #

    def _mock_get_logind_sessions(self) -> List[Mock]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_get_logind_sessions')

    def _mock_find_loopback_connections(self) -> List[Mock]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_find_loopback_connections')

    def _mock_map_scope_processes(self) -> Mapping[str, Set[int]]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_map_scope_processes')

    def _register_expected_sessions(self) -> None:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_sessions')

    #
    # Subclasses are encouraged to call these methods to construct Mocks
    #

    # Method signatures are useful for input validation, even if a LOT of them
    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @staticmethod
    def create_mock_logind_session(session_id: str,
                                   session_type: str,
                                   uid: int,
                                   tty: Optional[str],
                                   leader: int,
                                   scope: str):
        """Generate a Mock representing a logind session"""

        session = Mock()
        session.session_id = session_id
        session.session_type = session_type
        session.uid = uid
        session.tty = tty
        session.leader = leader
        session.scope = scope
        scope_path = f'/user.slice/user-{uid}.slice/{scope}'
        session.scope_path = scope_path
        return session

    @staticmethod
    def create_mock_loopback_connection(client_addr: Union[IPv4Address,
                                                           IPv6Address],
                                        client_port: int,
                                        client_pids: List[int],
                                        server_addr: Union[IPv4Address,
                                                           IPv6Address],
                                        server_port: int,
                                        server_pids: List[int]):
        """Generate a Mock representing an ss loopback connection"""

        connection = Mock()

        connection.client = Mock()
        connection.client.addr = client_addr
        connection.client.port = client_port
        connection.client.processes = []
        for client_pid in client_pids:
            process_mock = Mock()
            process_mock.pid = client_pid
            process_mock.__eq__ = MainLoopTestCase._mock_process_eq
            connection.client.processes.append(process_mock)

        connection.server = Mock()
        connection.server.addr = server_addr
        connection.server.port = server_port
        connection.server.processes = []
        for server_pid in server_pids:
            process_mock = Mock()
            process_mock.pid = server_pid
            process_mock.__eq__ = MainLoopTestCase._mock_process_eq
            connection.server.processes.append(process_mock)

        return connection

    def register_mock_session(self,
                              session_id: str,
                              session_type: str,
                              uid: int,
                              tty: Optional[str],
                              scope: str,
                              pids_and_tunnels: Mapping[int,
                                                        Tuple[List[int],
                                                              List[str]]]) -> None:
        """Generate a Mock representing a parsed session

        The strange type of pids_and_tunnels is a mapping from client PIDs,
        into a list of their backend integer PIDs and (separately) a list of
        their backend string session IDs.

        Unlike the create_mock_* functions, this one does not return its
        result. Instead, it saves it into a private array for later use.
        Notably, before a test case attempts to compare against the expected
        set of parsed sessions, it will run _resolve_tunneled_sessions and
        thereby "link" the string session ID tunnels to their full Session
        objects.
        """

        session = Mock()

        session.session = Mock()
        session.session.session_id = session_id
        session.session.session_type = session_type
        session.session.uid = uid
        session.session.tty = tty
        session.session.scope = scope
        session.__eq__ = MainLoopTestCase._mock_session_eq

        session.tty = Mock()
        session.tty.name = tty

        session.processes = []
        for client_pid, tunnel_spec in pids_and_tunnels.items():
            process = Mock()

            process.process = Mock()
            process.process.pid = client_pid
            process.process.display = None
            process.process.__eq__ = MainLoopTestCase._mock_process_eq
            process.__eq__ = MainLoopTestCase._mock_session_process_eq

            process.tunneled_processes = []
            for tunnel in tunnel_spec[0]:
                backend_process = Mock()
                backend_process.pid = tunnel
                backend_process.display = None
                backend_process.__eq__ = MainLoopTestCase._mock_process_eq
                process.tunneled_processes.append(backend_process)

            process.tunneled_sessions = []
            for tunnel in tunnel_spec[1]:
                # This will be resolved to a mock Session object later, by
                # the _resolve_tunneled_sessions method.
                process.tunneled_sessions.append(tunnel)

            session.processes.append(process)

        # Cache this object to allow for resolution; don't return it
        self._mocked_session_objects.append(session)

    #
    # Here are the actual test case methods -- these aren't usually overridden
    #

    def setUp(self):
        self._mocked_session_objects = []

        self._mocked_get_logind_sessions = Mock(
                side_effect=self._mock_get_logind_sessions
        )

        get_logind_sessions_patcher = patch(
                'stop_idle_sessions.logind.get_all_sessions',
                new=self._mocked_get_logind_sessions
        )
        get_logind_sessions_patcher.start()
        self.addCleanup(get_logind_sessions_patcher.stop)

        self._mocked_processes_in_scope_path = Mock(
                side_effect=self._mock_processes_in_scope_path
        )

        processes_in_scope_path_patcher = patch(
                'stop_idle_sessions.ps.processes_in_scope_path',
                new=self._mocked_processes_in_scope_path
        )
        processes_in_scope_path_patcher.start()
        self.addCleanup(processes_in_scope_path_patcher.stop)

        self._mocked_find_loopback_connections = Mock(
                side_effect=self._mock_find_loopback_connections
        )

        find_loopback_connections_patcher = patch(
                'stop_idle_sessions.ss.find_loopback_connections',
                new=self._mocked_find_loopback_connections
        )
        find_loopback_connections_patcher.start()
        self.addCleanup(find_loopback_connections_patcher.stop)

        tty_patcher = patch(
                'stop_idle_sessions.tty.TTY',
                new=Mock(side_effect=MainLoopTestCase._mock_tty())
        )
        tty_patcher.start()
        self.addCleanup(tty_patcher.stop)

        null_username_resolver_patcher = patch(
                'stop_idle_sessions.getent.uid_to_username',
                new=Mock(return_value=None)
        )
        null_username_resolver_patcher.start()
        self.addCleanup(null_username_resolver_patcher.stop)

        self._register_expected_sessions()
        self._resolve_tunneled_sessions()

    def test_parse_logind_sessions(self):
        """Ensure that the logind sessions are transformed appropriately"""

        expected_sessions = self._mocked_session_objects
        actual_sessions = stop_idle_sessions.main.load_sessions()

        matched_pairs = matchup_list_sets(expected_sessions,
                                          actual_sessions)

        # Matchups are done on the basis of session ID and PID; for the
        # purposes of this test, though, we have to go deeper than that.
        for expected, actual in matched_pairs:
            self.assertEqual(expected.session.uid,
                             actual.session.uid)
            self.assertEqual(expected.session.tty,
                             actual.session.tty)
            self.assertEqual(expected.session.scope,
                             actual.session.scope)
            self.assertEqual(expected.tty.name,
                             actual.tty.name)

            matched_pid_pairs = matchup_list_sets(expected.processes,
                                                  actual.processes)

            for expected_p, actual_p in matched_pid_pairs:
                matched_tunneled_processes = matchup_list_sets(
                        expected_p.tunneled_processes,
                        actual_p.tunneled_processes
                )
                self.assertEqual(len(matched_tunneled_processes),
                                 len(expected_p.tunneled_processes))
                self.assertEqual(len(matched_tunneled_processes),
                                 len(actual_p.tunneled_processes))

                matched_tunneled_sessions = matchup_list_sets(
                        expected_p.tunneled_sessions,
                        actual_p.tunneled_sessions
                )
                self.assertEqual(len(matched_tunneled_sessions),
                                 len(expected_p.tunneled_sessions))
                self.assertEqual(len(matched_tunneled_sessions),
                                 len(actual_p.tunneled_sessions))

            self.assertEqual(len(matched_pid_pairs),
                             len(expected.processes))
            self.assertEqual(len(matched_pid_pairs),
                             len(actual.processes))

        self.assertEqual(len(matched_pairs), len(expected_sessions))
        self.assertEqual(len(matched_pairs), len(actual_sessions))

    #
    # Internal methods used by test cases -- these should not be overridden
    #

    @staticmethod
    def _mock_process_eq(*args, **_):
        """Reimplementation of l_i_s_e.ps.Process.__eq__"""
        me, other = args
        if not hasattr(other, 'pid'):
            return False
        return me.pid == other.pid

    @staticmethod
    def _mock_session_process_eq(*args, **_):
        """Reimplementation of l_i_s_e.main.SessionProcess.__eq__"""
        me, other = args
        if not hasattr(other, 'process'):
            return False
        return MainLoopTestCase._mock_process_eq(me.process, other.process)

    @staticmethod
    def _mock_session_eq(*args, **_):
        """Reimplementation of l_i_s_e.main.Session.__eq__"""
        me, other = args
        if not hasattr(other, 'session'):
            return False
        if not hasattr(other.session, 'session_id'):
            return False
        return me.session.session_id == other.session.session_id

    @staticmethod
    def _mock_tty(return_mock: Optional[Mock] = None) -> Callable[[str], Mock]:
        """Factory function to create tty.TTY constructor functions"""

        def _inner_mock_tty(tty_name: str) -> Mock:
            if return_mock is None:
                my_return_mock = Mock()
            else:
                my_return_mock = return_mock
            my_return_mock.name = tty_name
            return my_return_mock

        return _inner_mock_tty

    def _mock_processes_in_scope_path(self, scope_path: str) -> List[Mock]:
        """Obtain a mocked set of process objects for a given scope path"""

        scope_processes = self._mock_map_scope_processes()
        for candidate_session_id, candidate_pids in scope_processes.items():
            if scope_path.endswith(f'session-{candidate_session_id}.scope'):
                processes = []
                for pid in sorted(candidate_pids):
                    process = Mock()
                    process.pid = pid
                    process.display = None
                    processes.append(process)
                return processes

        raise KeyError(f'could not find a scope for path {scope_path}')

    def _resolve_tunneled_sessions(self):
        """Revisit the mocked session objects and link tunneled sessions"""

        # Yes, this is a deeply-nested structure; nothing to be done about it
        # pylint: disable-next=too-many-nested-blocks
        for session in self._mocked_session_objects:
            for process in session.processes:
                for index, tunnel in enumerate(process.tunneled_sessions):
                    for find_session in self._mocked_session_objects:
                        if tunnel == find_session.session.session_id:
                            process.tunneled_sessions[index] = find_session

    #
    # Internal attributes used by test cases -- subclasses shouldn't use these
    #

    # The mocked logind.get_all_sessions which will provide sessions
    _mocked_get_logind_sessions: Mock

    # The mocked ps.processes_in_scope_path which will list members of cgroups
    _mocked_processes_in_scope_path: Mock

    # The mocked ss.find_loopback_connections which will provide connections
    _mocked_find_loopback_connections: Mock

    # Cached set of mocked main.Session objects; used to resolve sesssion_ids
    _mocked_session_objects: List[Mock]


def load_tests(*_):
    """Implementation of the load_tests protocol

    https://docs.python.org/3/library/unittest.html#load-tests-protocol

    All of the test cases should be added by the test_scenario*.py files. No
    unit tests should be run directly from this common file.

    We ignore the 1st argument (loader), 2nd argument (standard_tests), and
    3rd argument (pattern) and substitute a totally custom (empty) TestSuite.
    """
    return TestSuite()
