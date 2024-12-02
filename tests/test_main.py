"""Common logic for the main loop, shared across all scenarios"""


import datetime
from typing import Dict, List, Optional, Tuple
from unittest import TestCase, TestSuite
from unittest.mock import Mock, patch

from stop_idle_sessions.exception import SessionParseError
from stop_idle_sessions.list_set import matchup_list_sets
import stop_idle_sessions.logind
import stop_idle_sessions.main
import stop_idle_sessions.ps
import stop_idle_sessions.ss
import stop_idle_sessions.tty


class MainLoopTestCase(TestCase):
    """Unit testing for the main module

    This TestCase is meant to be subclassed, NOT run directly. The load_tests
    function at the bottom of this module prevents it from being
    auto-discovered.
    """

    #
    # Subclasses need to override these methods
    #

    def _mock_get_all_sessions(self) -> List[stop_idle_sessions.logind.Session]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_get_all_sessions')

    def _mock_find_loopback_connections(self) -> List[stop_idle_sessions.ss.LoopbackConnection]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_find_loopback_connections')

    def _mock_processes_in_scope_path(self,
                                      scope_path: str) -> List[stop_idle_sessions.ps.Process]:
        """Subclasses should override this method"""
        assert isinstance(scope_path, str)
        raise NotImplementedError('_mock_processes_in_scope_path')

    def _mock_uid_to_username(self, uid: int) -> str:
        """Subclasses should override this method"""
        assert isinstance(uid, int)
        raise NotImplementedError('_mock_uid_to_username')

    def _mock_retrieve_idle_time(self,
                                 display: str,
                                 xauthority: Optional[str]) -> Optional[datetime.timedelta]:
        """Subclasses should override this method"""
        assert isinstance(display, str)
        assert xauthority is None or isinstance(xauthority, str)
        raise NotImplementedError('_mock_retrieve_idle_time')

    def _mock_tty(self, name: str) -> stop_idle_sessions.tty.TTY:
        """Subclasses should override this method"""
        assert isinstance(name, str)
        raise NotImplementedError('_mock_tty')

    def _now(self) -> datetime.datetime:
        """Subclasses should override this method"""
        raise NotImplementedError('_now')

    def _excluded_users(self) -> List[str]:
        """Subclasses should override this method"""
        raise NotImplementedError('_excluded_users')

    def _expected_sessions(self) -> List[stop_idle_sessions.main.Session]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_sessions')

    def _expected_results(self) -> List[Tuple[bool, bool,
                                              Optional[datetime.timedelta]]]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_results')

    #
    # Here are the actual test case methods -- these aren't usually overridden
    #

    def setUp(self):
        get_all_sessions_patcher = patch(
                'stop_idle_sessions.logind.get_all_sessions',
                new=Mock(side_effect=self._wrap_mock_get_all_sessions)
        )
        get_all_sessions_patcher.start()
        self.addCleanup(get_all_sessions_patcher.stop)

        find_loopback_connections_patcher = patch(
                'stop_idle_sessions.ss.find_loopback_connections',
                new=Mock(side_effect=self._mock_find_loopback_connections)
        )
        find_loopback_connections_patcher.start()
        self.addCleanup(find_loopback_connections_patcher.stop)

        processes_in_scope_path_patcher = patch(
                'stop_idle_sessions.ps.processes_in_scope_path',
                new=Mock(side_effect=self._mock_processes_in_scope_path)
        )
        processes_in_scope_path_patcher.start()
        self.addCleanup(processes_in_scope_path_patcher.stop)

        uid_to_username_patcher = patch(
                'stop_idle_sessions.getent.uid_to_username',
                new=Mock(side_effect=self._mock_uid_to_username)
        )
        uid_to_username_patcher.start()
        self.addCleanup(uid_to_username_patcher.stop)

        retrieve_idle_time_patcher = patch(
                'stop_idle_sessions.x11.X11SessionProcesses.retrieve_idle_time',
                new=Mock(side_effect=self._mock_retrieve_idle_time)
        )
        retrieve_idle_time_patcher.start()
        self.addCleanup(retrieve_idle_time_patcher.stop)

        tty_patcher = patch(
                'stop_idle_sessions.tty.TTY',
                new=Mock(side_effect=self._mock_tty)
        )
        tty_patcher.start()
        self.addCleanup(tty_patcher.stop)

    def test_parse_logind_sessions(self):
        """Ensure that the logind sessions are transformed appropriately"""

        expected_sessions = self._expected_sessions()
        actual_sessions = stop_idle_sessions.main.load_sessions()

        matched_pairs = matchup_list_sets(expected_sessions,
                                          actual_sessions)

        # Matchups are done on the basis of session ID and PID; for the
        # purposes of this test, though, we have to go deeper than that.
        for expected, actual in matched_pairs:
            self.assertEqual(expected.session.uid,
                             actual.session.uid)
            self.assertTrue(
                    stop_idle_sessions.tty.TTY.compare(
                        expected.tty,
                        actual.tty
                    )
            )
            self.assertEqual(expected.session.scope,
                             actual.session.scope)

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

    def test_session_results(self):
        """Ensure that each session exhibits the expected results

        The tuple for _expected_results is as follows:
          (skipped_exempt: bool, terminated: bool, idle_metric: timedelta)
        """

        actual_sessions = stop_idle_sessions.main.load_sessions()
        expected_results = self._expected_results()
        self.assertEqual(len(actual_sessions), len(expected_results))

        for session, (skipped_exempt,
                      terminated,
                      idle_metric) in zip(actual_sessions,
                                          expected_results):
            actual_idle_metric: Optional[datetime.timedelta] = None

            if idle_metric is None:
                with self.assertRaises(SessionParseError):
                    stop_idle_sessions.main.compute_idleness_metric(session,
                                                                    self._now())
            else:
                actual_idle_metric = stop_idle_sessions.main.compute_idleness_metric(
                        session,
                        self._now()
                )
                self.assertAlmostEqual(idle_metric,
                                       actual_idle_metric,
                                       delta=datetime.timedelta(seconds=1))

            skip_ineligible, _ = stop_idle_sessions.main.skip_ineligible_session(
                    session,
                    self._excluded_users()
            )

            if skip_ineligible:
                self.assertTrue(skipped_exempt)
            else:
                self.assertFalse(skipped_exempt)

                if actual_idle_metric is None:
                    raise RuntimeError(f"For id={session.session.session_id}, "
                                       f"indicated that it should not be "
                                       f"skipped, but no timedelta provided")

                if actual_idle_metric >= datetime.timedelta(seconds=15 * 60):
                    session.session.kill_session_leader()

                kill_mock = self._mocked_killed_session_leaders[session.session.session_id]
                if terminated:
                    kill_mock.assert_called_once()
                else:
                    kill_mock.assert_not_called()

    #
    # Internal methods used by test cases -- these should not be overridden
    #

    def _wrap_mock_get_all_sessions(self) -> List[stop_idle_sessions.logind.Session]:
        """Wrap the _mock_get_all_sessions output to insert kill_session_leader

        When this particular Mock is created and added to the mocks created by
        the scenario, it needs to be tracked locally to provide assertions.
        """

        self._mocked_killed_session_leaders = {}

        sessions = self._mock_get_all_sessions()
        for session in sessions:
            kill_mock = Mock()

            self._mocked_killed_session_leaders[session.session_id] = kill_mock

            # Python type checkers cannot detect that this returned session
            # object is actually a Mock -- but Python itself certainly can.
            mock_session: Mock = session   # type: ignore
            mock_session.configure_mock(kill_session_leader=kill_mock)

        return sessions

    #
    # Internal attributes used by test cases -- subclasses shouldn't use these
    #

    # Session IDs for any sessions terminated by _mocked_kill_session_leader
    _mocked_killed_session_leaders: Dict[str, Mock]


def load_tests(*_):
    """Implementation of the load_tests protocol

    https://docs.python.org/3/library/unittest.html#load-tests-protocol

    All of the test cases should be added by the test_scenario*.py files. No
    unit tests should be run directly from this common file.

    We ignore the 1st argument (loader), 2nd argument (standard_tests), and
    3rd argument (pattern) and substitute a totally custom (empty) TestSuite.
    """
    return TestSuite()
