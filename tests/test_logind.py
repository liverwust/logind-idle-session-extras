"""Unit testing for the logind module"""


import unittest

from .logind import MockGio
import logind_idle_session_extras.logind


_GIO_TARGET = "logind_idle_session_extras.logind.Gio"


class LogindTestCase(unittest.TestCase):
    """Unit testing for the logind module"""

    def test_parsing_nominal_logind_bus_state(self):
        """Test parsing of a nominal logind bus state"""

        mock_gio = MockGio({
            "1267": {
                "Id": "1267",
                "User": "1002",
                "TTY": "pts/2",
                "Scope": "session-1267.scope",
                "Leader": "952165"
            },
            "1301": {
                "Id": "1301",
                "User": "0",
                "TTY": "pts/1",
                "Scope": "session-1301.scope",
                "Leader": "994974"
            },
            "1337": {
                "Id": "1337",
                "User": "1002",
                "TTY": "pts/0",
                "Scope": "session-1337.scope",
                "Leader": "1050298"
            },
            "c1": {
                "Id": "c1",
                "User": "42",
                "TTY": "tty1",
                "Scope": "session-c1.scope",
                "Leader": "5655"
            }
        })

        expected_info_checks = [
            {
                "session_id": "1267",
                "uid": 1002,
                "tty": "pts/2",
                "leader": 952165,
                "scope": "session-1267.scope",
                "scope_path": "/user.slice/user-1002.slice/session-1267.scope"
            },
            {
                "session_id": "1301",
                "uid": 0,
                "tty": "pts/1",
                "leader": 994974,
                "scope": "session-1301.scope",
                "scope_path": "/user.slice/user-0.slice/session-1301.scope"
            },
            {
                "session_id": "1337",
                "uid": 1002,
                "tty": "pts/0",
                "leader": 1050298,
                "scope": "session-1337.scope",
                "scope_path": "/user.slice/user-1002.slice/session-1337.scope"
            },
            {
                "session_id": "c1",
                "uid": 42,
                "tty": "tty1",
                "leader": 5655,
                "scope": "session-c1.scope",
                "scope_path": "/user.slice/user-42.slice/session-c1.scope"
            }
        ]

        #import pdb;pdb.set_trace()

        with mock_gio.patch(_GIO_TARGET, check_all_sessions=True):
            m = logind_idle_session_extras.logind.Manager()
            sessions = list(m.get_all_sessions())
            self.assertEqual(len(sessions), 4)

            for expected_info_check in expected_info_checks:
                for idx, session in enumerate(sessions):
                    matches = True
                    for attr, value in expected_info_check.items():
                        if getattr(session, attr) != value:
                            matches = False
                            break

                    if matches:
                        del(sessions[idx])
                        break

            self.assertEqual(len(sessions), 0)
