"""Common logind testing logic shared across all scenarios"""


from functools import partial
import pdb
import re
from typing import Any, List, Mapping
from unittest import TestCase, TestSuite
from unittest.mock import ANY, Mock, patch

import logind_idle_session_extras.logind


_SESSION_NODE_RE = r'^/org/freedesktop/login1/session/([^/]+)$'


class LogindTestCase(TestCase):
    """Unit testing for the logind module"""

    # The mocked Gio object created by _mock_gio()
    _mocked_gio: Mock

    # Cached list of sessions, to allow for later assertions
    _sessions: Mapping[str, Mock]

    #
    # Subclasses need to override these methods
    #

    def _mock_gio_results_spec(self) -> Mapping[str, Mapping[str, str]]:
        """Subclasses should override this method"""
        raise NotImplementedError('_mock_gio')

    def _expected_logind_sessions(self) -> List[Mapping[str, Any]]:
        """Subclasses should override this method"""
        raise NotImplementedError('_expected_logind_sessions')

    #
    # Here are the actual test case methods -- these should not be overridden
    #

    def setUp(self):
        self._sessions = {}

        self._mocked_gio = self._mock_gio(self._mock_gio_results_spec())
        mock_gio_obj_patch = patch('logind_idle_session_extras.logind.Gio',
                                   new=self._mocked_gio)
        mock_gio_obj_patch.start()
        self.addCleanup(mock_gio_obj_patch.stop)

    def test_logind_interface_parsed_objects(self):
        """Ensure that objects are appropriately parsed from the logind API"""

        sessions = list(logind_idle_session_extras.logind.get_all_sessions())
        self.assertEqual(len(sessions), 4)

        for expected_info_check in self._expected_logind_sessions():
            for idx, session in enumerate(sessions):
                matches = True
                for attr, value in expected_info_check.items():
                    if getattr(session, attr) != value:
                        matches = False
                        break

                if matches:
                    del sessions[idx]
                    break

        self.assertEqual(len(sessions), 0)
        self._assert_fully_exercised()

    #
    # Internal methods used by test cases -- these should not be overridden
    #

    def _mock_gio(self, results_spec: Mapping[str, Mapping[str, Any]]) -> Mock:
        """Mock the Gio object to simulate logind responses

        The core of the resulting object is the results_spec, which is a nested
        mapping. The outer layer maps session IDs to their own inner mappings. The
        inner layer maps string parameter names (e.g., "Leader") to arbitrary
        values. These are then returned as cached properties for each mocked
        Session.
        """

        mock_obj = Mock()

        mock_obj.bus_get_sync = Mock()
        mock_obj.BusType = Mock()
        mock_obj.BusType.SYSTEM = 'SYSTEM'
        mock_obj.DBusProxyFlags = Mock()
        mock_obj.DBusCallFlags = Mock()

        mock_obj.DBusProxy = Mock()
        mock_obj.DBusProxy.new_sync = Mock(
                side_effect=self._dbus_proxy_new_sync
        )

        # We are mocking this object -- nothing is protected from us!
        # pylint: disable=protected-access
        mock_obj._manager = Mock()
        mock_obj._manager.call_sync = Mock(
                side_effect=self._manager_call_sync
        )

        self._sessions: Mapping[str, Mock] = {}
        for session_id, spec in results_spec.items():
            self._sessions[session_id] = Mock()
            self._sessions[session_id].get_cached_property = Mock(
                    side_effect=partial(
                        self._session_get_cached_property,
                        spec
                    )
            )

        return mock_obj

    def _dbus_proxy_new_sync(self, *args):
        """Return either a mocked Manager or a mocked Session"""

        # We are mocking this object -- nothing is protected from us!
        # pylint: disable=protected-access
        if args[5] == "org.freedesktop.login1.Manager":
            return self._mocked_gio._manager
        if args[5] == "org.freedesktop.login1.Session":
            session_id_match = re.match(_SESSION_NODE_RE, args[4])
            if session_id_match is None:
                raise ValueError(f'invalid session node {args[4]}')
            return self._sessions[session_id_match.group(1)]
        raise KeyError('Unknown D-Bus interface: {args[5]}')

    def _manager_call_sync(self, *_):
        """Return a list of Session results with the set of spec'd IDs"""

        packed_result = Mock()
        packed_result.unpack = Mock(side_effect=lambda: [
            list(map(lambda x: [x], self._sessions.keys()))
        ])
        return packed_result

    def _session_get_cached_property(self, spec: Mapping[str, Any], *args):
        """Return a session API object that can return specified values"""

        packed_result = Mock()
        packed_result.get_string = Mock(
                side_effect=lambda: str(spec[args[0]])
        )
        packed_result.get_uint32 = Mock(
                side_effect=lambda: int(spec[args[0]])
        )

        # This is a special datatype for User, listed in the docs as (uo)
        # https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
        if args[0] == "User":
            packed_result.unpack = Mock(side_effect=lambda: [
                    int(spec[args[0]])
            ])

        return packed_result

    def _assert_fully_exercised(self):
        """Run assertions to ensure that the entire GioMock was exercised"""

        self._mocked_gio.bus_get_sync.assert_called()

        self._mocked_gio.DBusProxy.new_sync.assert_any_call(
                ANY,
                ANY,
                ANY,
                'org.freedesktop.login1',
                '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager',
                ANY
        )

        self._mocked_gio.DBusProxy.new_sync.assert_any_call(
                ANY,
                ANY,
                ANY,
                'org.freedesktop.login1',
                ANY,
                'org.freedesktop.login1.Session',
                ANY
        )

        # We are mocking this object -- nothing is protected from us!
        # pylint: disable=protected-access
        self._mocked_gio._manager.call_sync.assert_called_with(
                'ListSessions',
                ANY,
                ANY,
                ANY,
                ANY
        )

        for session_id, session in self._sessions.items():
            try:
                session.get_cached_property.assert_called()
            except AssertionError as e:
                raise AssertionError(f'Session ID {session_id}') from e


def load_tests(*_):
    """Implementation of the load_tests protocol

    https://docs.python.org/3/library/unittest.html#load-tests-protocol

    All of the test cases should be added by the test_scenario*.py files. No
    unit tests should be run directly from this common file.

    We ignore the 1st argument (loader), 2nd argument (standard_tests), and
    3rd argument (pattern) and substitute a totally custom (empty) TestSuite.
    """
    return TestSuite()
