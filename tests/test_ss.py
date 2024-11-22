"""Common network loopback testing logic shared across all scenarios"""


from ipaddress import IPv4Address, IPv6Address
from os.path import basename
from typing import List, Set, Tuple, Union
from unittest import TestCase, TestSuite
from unittest.mock import Mock, patch

from stop_idle_sessions.list_set import compare_list_sets
import stop_idle_sessions.ps
import stop_idle_sessions.ss


class LoopbackConnectionTestCase(TestCase):
    """Unit testing for the ss module

    This TestCase is meant to be subclassed, NOT run directly. The load_tests
    function at the bottom of this module prevents it from being
    auto-discovered.
    """

    #
    # Subclasses need to override these methods
    #

    def _mock_raw_ss_output(self) -> str:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_raw_ss_output')

    def _expected_listening_ports(self) -> Set[int]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_listening_ports')

    def _expected_peer_pairs(self) -> Set[Tuple[Union[IPv4Address,
                                                      IPv6Address], int]]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_peer_pairs')

    def _expected_connections(self) -> List[stop_idle_sessions.ss.LoopbackConnection]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_loopback_connections')

    #
    # Here are the actual test case methods -- these aren't usually overridden
    #

    def setUp(self):
        self._mocked_subprocess_run = Mock(
                side_effect=self._subprocess_run_with_check
        )

        mocked_subprocess_run_patcher = patch('subprocess.run',
                                              new=self._mocked_subprocess_run)
        mocked_subprocess_run_patcher.start()
        self.addCleanup(mocked_subprocess_run_patcher.stop)

    def test_three_stages_parsed_objects(self):
        """Ensure that each of the three parsing stages performs correctly

        This reaches a _bit_ more deeply into the code than a unit test
        perhaps should -- or at least it makes a few too many assertions --
        but it is useful to keep track of some of the inner workings to make
        sure everything is handled properly (without mocking internals).
        """

        invoke = stop_idle_sessions.ss.SSInvocation()
        invoke.run()

        expected_listening_ports = self._expected_listening_ports()
        actual_listening_ports=set(map(lambda s: s.port,
                                       invoke.listen_sockets))
        self.assertSetEqual(expected_listening_ports,
                            actual_listening_ports)

        expected_peer_pairs = self._expected_peer_pairs()
        actual_peer_pairs = set(map(lambda x: (x[1], x[2]),
                                    invoke.established_sockets))
        self.assertSetEqual(expected_peer_pairs,
                            actual_peer_pairs)

        expected_connections = self._expected_connections()
        actual_connections = invoke.loopback_connections
        self.assertTrue(compare_list_sets(expected_connections,
                                          actual_connections))

    #
    # Internal methods used by test cases -- these should not be overridden
    #

    def _subprocess_run_with_check(self, *args, **_) -> Mock:
        """Mock the subprocess.run call with a check for 'ss' command"""

        if basename(args[0][0]) != "ss":
            raise ValueError(f"Unexpected command {args[0]}")
        completed_process = Mock()
        completed_process.stdout = self._mock_raw_ss_output()
        return completed_process

    #
    # Internal attributes used by test cases -- subclasses shouldn't use these
    #

    # The mocked subprocess.run which will provide a particular stdout
    _mocked_subprocess_run: Mock


def load_tests(*_):
    """Implementation of the load_tests protocol

    https://docs.python.org/3/library/unittest.html#load-tests-protocol

    All of the test cases should be added by the test_scenario*.py files. No
    unit tests should be run directly from this common file.

    We ignore the 1st argument (loader), 2nd argument (standard_tests), and
    3rd argument (pattern) and substitute a totally custom (empty) TestSuite.
    """
    return TestSuite()
