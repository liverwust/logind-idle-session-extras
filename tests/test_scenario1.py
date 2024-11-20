"""Scenario 1 for unit-testing of logind-idle-sessions-extras

In Scenario 1, there is a single active user with one SSH session and one
non-idle VNC session. The SSH session is actively tunneled into the VNC
session. Separately, the root user is SSH'd into the system (for observation)
and there is an idle GDM session running.
"""


from typing import Any, List, Mapping

from . import test_logind


class Scenario1LogindTestCase(test_logind.LogindTestCase):
    """Scenario1 unit testing for the logind module

    See the docstring for the test_scenario1 module for an overall description
    of Scenario 1 (single active user w/ VNC).
    """

    def _mock_gio_results_spec(self) -> Mapping[str, Mapping[str, str]]:
        """Input data to populate the mock Gio object (logind API)"""
        return {
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
        }

    def _expected_logind_sessions(self) -> List[Mapping[str, Any]]:
        """Expected set of logind session attributes to be returned"""
        return [
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
