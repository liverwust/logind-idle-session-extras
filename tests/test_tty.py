"""Test cases for TTY/PTY interactions and atime updates"""


from contextlib import contextmanager
import datetime.datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from logind_idle_session_extras import tty


TTY_TARGET = "tty.TTY"


@contextmanager
def patch_tty(atime: datetime.datetime,
              mtime: datetime.datetime,
              tty_target: str = TTY_TARGET):
    """Convenience patch wrapper for mocking the TTY object

    As with mock.patch normally, the "target" is the fully-qualified
    attribute name of the "TTY" class object which should be replaced by this
    mocked TTY object. See also:
    https://docs.python.org/3.6/library/unittest.mock.html#where-to-patch
    """

    new_mock = Mock(tty.TTY)
    new_mock._initialize_times = Mock(return_value=(atime, mtime))
    new_mock._os_touch_times = Mock()

    with patch(tty_target, new_mock):
        yield new_mock
        new_mock._initialize_times.assert_called()


class TtyUpdateTimeTestCase(TestCase):
    """Ensure that the appropriate internal methods are called by TTY"""

    def test_internal_methods_called(self):
        """Ensure that the appropriate internal methods are called by TTY"""

        old_atime = datetime.datetime(2024, 1, 2, 3, 4, 5)
        old_mtime = datetime.datetime(2024, 1, 2, 3, 4, 6)

        new_time = datetime.datetime(2024, 1, 2, 3, 4, 10)

        with patch_tty(old_atime, old_mtime) as mock_tty:
            tty = tty.TTY('pts/4')
            self.assertEqual(tty.atime, old_atime)
            self.assertEqual(tty.mtime, old_mtime)

            tty.touch_times(new_time)
            self.assertEqual(tty.atime, new_time)
            self.assertEqual(tty.mtime, new_time)

            mock_tty._os_touch_times.assert_called_once_with(tty,
                                                             new_time,
                                                             new_time)
