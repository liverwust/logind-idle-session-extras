"""Test cases for TTY/PTY interactions and atime updates"""


from contextlib import contextmanager
import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

# TODO: I would prefer to import the shorter name, but it causes a
# ModuleNotFoundError when attempting to patch _from inside this module_
#from logind_idle_session_extras import tty
import logind_idle_session_extras.tty


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

    mock_initialize_times = Mock(return_value=(atime, mtime))
    mock_touch_times = Mock()
    with patch(tty_target + "._os_initialize_times",
               new=mock_initialize_times):
        with patch(tty_target + "._os_touch_times",
                   new=mock_touch_times):
            yield (mock_initialize_times, mock_touch_times)
            mock_initialize_times.assert_called()


class TtyUpdateTimeTestCase(TestCase):
    """Ensure that the appropriate internal methods are called by TTY"""

    def test_internal_methods_called(self):
        """Ensure that the appropriate internal methods are called by TTY"""

        old_atime = datetime.datetime(2024, 1, 2, 3, 4, 5)
        old_mtime = datetime.datetime(2024, 1, 2, 3, 4, 6)

        new_time = datetime.datetime(2024, 1, 2, 3, 4, 10)

        with patch_tty(old_atime,
                       old_mtime,
                       'logind_idle_session_extras.tty.TTY') as mock_tty:
            tty_obj = logind_idle_session_extras.tty.TTY('pts/4')
            self.assertEqual(tty_obj.atime, old_atime)
            self.assertEqual(tty_obj.mtime, old_mtime)

            tty_obj.touch_times(new_time)
            self.assertEqual(tty_obj.atime, new_time)
            self.assertEqual(tty_obj.mtime, new_time)

            # Index 1 corresponding to _os_touch_times
            mock_tty[1].assert_called_once_with('/dev/pts/4', new_time, new_time)
