"""Unit testing for getent passwd command wrapper"""


from unittest import TestCase
from unittest.mock import Mock, patch

from stop_idle_sessions.exception import SessionParseError
import stop_idle_sessions.getent


class UidToUsernameTestCase(TestCase):
    """Unit-testing for the getent passwd command wrapper"""

    def test_successful_name_resolution(self):
        """Verify the module behavior when the user does exist"""
        completed_process = Mock()
        completed_process.stdout = "auser:x:1000:1000:A User:/home/auser:/bin/bash\n"
        completed_process.stderr = ""
        completed_process.returncode = 0

        with patch('subprocess.run',
                   new=Mock(return_value=completed_process)) as mock_run:
            actual_user = stop_idle_sessions.getent.uid_to_username(1000)
            self.assertEqual('auser', actual_user)
            mock_run.assert_called()

    def test_unsuccessful_name_resolution(self):
        """Verify the module behavior when the user does not exist"""
        completed_process = Mock()
        completed_process.stdout = ""
        completed_process.stderr = ""
        completed_process.returncode = 2

        with patch('subprocess.run',
                   new=Mock(return_value=completed_process)) as mock_run:
            with self.assertRaises(SessionParseError):
                stop_idle_sessions.getent.uid_to_username(1000)
            mock_run.assert_called()
