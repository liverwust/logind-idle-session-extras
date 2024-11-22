"""Common process table / cgroup testing logic shared across all scenarios"""


from typing import List, Mapping
from unittest import TestCase, TestSuite
from unittest.mock import Mock, mock_open, patch

import stop_idle_sessions.ps


class CgroupPidsTestCase(TestCase):
    """Unit testing for the ps module

    This TestCase is meant to be subclassed, NOT run directly. The load_tests
    function at the bottom of this module prevents it from being
    auto-discovered.
    """

    #
    # Subclasses need to override these methods
    #

    def _mock_process_specs(self) -> Mapping[int, str]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_process_specs')

    def _expected_process_objects(self) -> List[stop_idle_sessions.ps.Process]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_logind_sessions')

    #
    # Here are the actual test case methods -- these aren't usually overridden
    #

    def setUp(self):
        self._mock_psutil_process(self._mock_process_specs())

        mock_psutil_process_patcher = patch('psutil.Process',
                                            new=self._mocked_psutil_process)
        mock_psutil_process_patcher.start()
        self.addCleanup(mock_psutil_process_patcher.stop)

    def test_ps_interface_parsed_objects(self):
        """Ensure that processes are appropriately parsed from the cgroup"""

        expected_processes = self._expected_process_objects()
        actual_processes = list(
                stop_idle_sessions.ps.processes_in_scope_path(
                    "/user.slice/user-1000.slice/session-1024.scope",
                    open_func=self._mocked_open
                )
        )

        self._mocked_psutil_process.assert_called()
        self.assertListEqual(expected_processes, actual_processes)

    #
    # Internal methods used by test cases -- these should not be overridden
    #

    def _mock_psutil_process(self, process_specs: Mapping[int, str]):
        """Mock the sysfs directory file and process table for a set of PIDs

        Each PID may be associated with its own "command line" (e.g.
        /usr/sbin/sshd [...args...]).
        """

        self._mocked_processes = {}

        self._mocked_psutil_process = Mock(side_effect=self._psutil_process_init)
        for pid, cmdline in process_specs.items():
            self._mocked_processes[pid] = Mock()
            self._mocked_processes[pid].pid = pid
            self._mocked_processes[pid].cmdline = Mock(return_value=cmdline.split())
            self._mocked_processes[pid].environ = Mock(return_value={})

        self._mocked_open = mock_open(read_data=self._cgroup_procs_content)

    @property
    def _cgroup_procs_content(self) -> str:
        """File contents of the simulated cgroup.procs file

        The PIDs from this Mock are guaranteed to be sorted. This appears to
        be true for the real sysfs too (though it's not clear whether that is
        a specified behavior or an implementation detail).
        """
        return "".join(map(lambda x: f"{x}\n",
                           sorted(self._mocked_processes.keys())))

    def _psutil_process_init(self, *args, **_) -> Mock:
        """Mock the initialization of a Process by looking up a PID"""
        return self._mocked_processes[int(args[0])]

    #
    # Internal attributes used by test cases -- subclasses shouldn't use these
    #

    # The mocked psutil.Process object created by _mock_psutil_process()
    _mocked_psutil_process: Mock

    # Individually-mocked Process objects which have been cached
    _mocked_processes: Mapping[int, Mock]

    # A mocked variant of the builtin open() function
    _mocked_open: Mock


def load_tests(*_):
    """Implementation of the load_tests protocol

    https://docs.python.org/3/library/unittest.html#load-tests-protocol

    All of the test cases should be added by the test_scenario*.py files. No
    unit tests should be run directly from this common file.

    We ignore the 1st argument (loader), 2nd argument (standard_tests), and
    3rd argument (pattern) and substitute a totally custom (empty) TestSuite.
    """
    return TestSuite()
