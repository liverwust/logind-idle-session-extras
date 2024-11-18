"""Mock and unit-test the process table information from /sys/fs/cgroup"""


from contextlib import contextmanager
from typing import Callable, Mapping, Tuple
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

from logind_idle_session_extras import ps


PROCESS_TARGET = "psutil.Process"


class MockCgroup:
    """Mock the sysfs directory file and process table for a set of PIDs

    Each PID may be associated with its own "command name" (e.g., sshd) and
    "command line" (e.g. /usr/sbin/sshd [...args...]). When constructing the
    MockCgroup, the first element in the tuple is the "comm" and the second is
    the "cmdline."
    """

    # Use the open_mock attribute to pass to processes_in_scope_path
    open_mock: Callable

    def __init__(self, process_specs: Mapping[int, Tuple[str, str]]):
        self._pids = list(process_specs.keys())
        self.open_mock = mock_open(read_data=self.cgroup_procs_content)

        self._psutil_process = Mock(side_effect=self._psutil_process_init)
        self._processes = {}
        for pid, (comm, cmdline) in process_specs.items():
            self._processes[pid] = Mock()
            self._processes[pid].pid = pid
            self._processes[pid].name = Mock(return_value=comm)
            self._processes[pid].cmdline = Mock(return_value=cmdline)

    @property
    def cgroup_procs_content(self) -> str:
        """File contents of the simulated cgroup.procs file

        The PIDs from this Mock are guaranteed to be sorted. This appears to
        be true for the real sysfs too (though it's not clear whether that is
        a specified behavior or an implementation detail).
        """
        return "".join(map(lambda x: "{}\n".format(x),
                           sorted(self._pids)))

    def _psutil_process_init(self, *args, **_):
        """Mock the initialization of a Process by looking up a PID"""
        return self._processes[int(args[0])]

    @contextmanager
    def patch(self, process_target: str = PROCESS_TARGET):
        """Convenience patch wrapper for MockCgroup, with assertions

        As with mock.patch normally, the "target" is the fully-qualified
        attribute name of the "Gio" object which should be replaced by this
        MockGio. See also:
        https://docs.python.org/3.6/library/unittest.mock.html#where-to-patch
        """

        with patch(process_target, self._psutil_process) as process_mock:
            yield self
            process_mock.assert_called()


class PIDMapTestCase(TestCase):
    """Ensure that the MockCgroup works properly"""

    def test_mock_cgroup(self):
        """Ensure that the MockCgroup works properly"""

        process_specs = {
                1345: ("hello-world",
                       "/usr/bin/hello-world test1 test2"),
                1366: ("sleep",
                       "/usr/bin/sleep 180"),
                1391: ("sshd",
                       "/usr/sbin/sshd: user@notty")
        }

        cgroup_mock = MockCgroup(process_specs)

        with cgroup_mock.patch():
            actual_processes = list(ps.processes_in_scope_path(
                    "/user.slice/user-1000.slice/session-1024.scope",
                    open_func=cgroup_mock.open_mock
            ))

            self.assertEqual(actual_processes[0].pid,
                             1345)
            self.assertEqual((actual_processes[0].name(),
                              actual_processes[0].cmdline()),
                             process_specs[1345])

            self.assertEqual(actual_processes[1].pid,
                             1366)
            self.assertEqual((actual_processes[1].name(),
                              actual_processes[1].cmdline()),
                             process_specs[1366])

            self.assertEqual(actual_processes[2].pid,
                             1391)
            self.assertEqual((actual_processes[2].name(),
                              actual_processes[2].cmdline()),
                             process_specs[1391])
