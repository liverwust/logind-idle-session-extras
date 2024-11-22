"""TTY/PTY and atime update test cases"""


import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

import stop_idle_sessions.tty


class TtyUpdateTimeTestCase(TestCase):
    """Ensure that the appropriate internal methods are called by TTY"""

    def setUp(self):
        self._mock_os_initialize_times = Mock(
                return_value=(self._mock_old_atime,
                              self._mock_old_mtime)
        )

        mock_os_initialize_times_patcher = patch(
                'stop_idle_sessions.tty.TTY._os_initialize_times',
                new=self._mock_os_initialize_times
        )
        mock_os_initialize_times_patcher.start()
        self.addCleanup(mock_os_initialize_times_patcher.stop)

        self._mock_os_touch_times = Mock()

        mock_os_initialize_times_patcher = patch(
                'stop_idle_sessions.tty.TTY._os_touch_times',
                new=self._mock_os_touch_times
        )
        mock_os_initialize_times_patcher.start()
        self.addCleanup(mock_os_initialize_times_patcher.stop)

    @property
    def _mock_old_atime(self) -> datetime.datetime:
        """Set the initial value for the atime on the mocked TTY"""
        return datetime.datetime(2024, 1, 2, 3, 4, 5)

    @property
    def _mock_old_mtime(self) -> datetime.datetime:
        """Set the initial value for the mtime on the mocked TTY"""
        return datetime.datetime(2024, 1, 2, 3, 4, 6)

    @property
    def _mock_replaced_time(self) -> datetime.datetime:
        """Set the initial value for the updated times on the mocked TTY"""
        return datetime.datetime(2024, 1, 2, 3, 4, 10)

    def test_internal_methods_called(self):
        """Ensure that the appropriate internal methods are called by TTY"""

        tty_obj = stop_idle_sessions.tty.TTY('pts/4')
        self.assertEqual(tty_obj.atime, self._mock_old_atime)
        self.assertEqual(tty_obj.mtime, self._mock_old_mtime)

        tty_obj.touch_times(self._mock_replaced_time)
        self.assertEqual(tty_obj.atime, self._mock_replaced_time)
        self.assertEqual(tty_obj.mtime, self._mock_replaced_time)

        # Index 1 corresponding to _os_touch_times
        self._mock_os_touch_times.assert_called_once_with(
                '/dev/pts/4',
                self._mock_replaced_time,
                self._mock_replaced_time
        )

    # Overridden _os_initialize_times method for reading timestamps
    _mock_os_initialize_times: Mock

    # Overridden _os_touch_times method for writing timestamps
    _mock_os_touch_times: Mock
