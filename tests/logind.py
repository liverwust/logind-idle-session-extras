"""Mock session information from systemd-logind"""


from contextlib import contextmanager
from functools import partial
import re
from typing import Any, Mapping
from unittest import mock


_SESSION_NODE_RE = r'^/org/freedesktop/login1/session/([^/]+)$'


class MockGio:
    """Enable replacing the Gio object to simulate logind responses

    The core of this Patcher class is the results_spec, which is a nested
    mapping. The outer layer maps session IDs to their own inner mappings. The
    inner layer maps string parameter names (e.g., "Leader") to arbitrary
    values. These are then returned as cached properties for each mocked
    Session.
    """

    def __init__(self, results_spec: Mapping[str, Mapping[str, Any]]):
        self.bus_get_sync = mock.Mock()
        self.BusType = mock.Mock()
        self.BusType.SYSTEM = 'SYSTEM'
        self.DBusProxyFlags = mock.Mock()
        self.DBusCallFlags = mock.Mock()

        self.DBusProxy = mock.Mock()
        self.DBusProxy.new_sync = mock.Mock(
                side_effect=self._dbus_proxy_new_sync
        )

        self._manager = mock.Mock()
        self._manager.call_sync = mock.Mock(
                side_effect=self._manager_call_sync
        )

        self._sessions: Mapping[str, mock.Mock] = {}
        for session_id, spec in results_spec.items():
            self._sessions[session_id] = mock.Mock()
            self._sessions[session_id].get_cached_property = mock.Mock(
                    side_effect=partial(
                        self._session_get_cached_property,
                        spec
                    )
            )

    def _dbus_proxy_new_sync(self, *args):
        """Return either a mocked Manager or a mocked Session"""

        if args[5] == "org.freedesktop.login1.Manager":
            return self._manager
        elif args[5] == "org.freedesktop.login1.Session":
            session_id_match = re.match(_SESSION_NODE_RE, args[4])
            if session_id_match is None:
                raise ValueError('invalid session node {}'.format(args[4]))
            return self._sessions[session_id_match.group(1)]

    def _manager_call_sync(self, *_):
        """Return a list of Session results with the set of spec'd IDs"""

        packed_result = mock.Mock()
        packed_result.unpack = mock.Mock(side_effect=lambda: [
            list(map(lambda x: [x], self._sessions.keys()))
        ])
        return packed_result

    def _session_get_cached_property(self, spec: Mapping[str, Any], *args):
        """Return a session API object that can return specified values"""

        packed_result = mock.Mock()
        packed_result.get_string = mock.Mock(
                side_effect=lambda: str(spec[args[0]])
        )
        packed_result.get_uint32 = mock.Mock(
                side_effect=lambda: int(spec[args[0]])
        )

        # This is a special datatype for User, listed in the docs as (uo)
        # https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
        if args[0] == "User":
            packed_result.unpack = mock.Mock(side_effect=lambda: [
                    int(spec[args[0]])
            ])

        return packed_result

    def assert_fully_exercised(self, check_all_sessions: bool = False):
        """Run assertions to ensure that the entire GioMock was exercised"""

        self.bus_get_sync.assert_called()

        self.DBusProxy.new_sync.assert_any_call(
                mock.ANY,
                mock.ANY,
                mock.ANY,
                'org.freedesktop.login1',
                '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager',
                mock.ANY
        )

        self.DBusProxy.new_sync.assert_any_call(
                mock.ANY,
                mock.ANY,
                mock.ANY,
                'org.freedesktop.login1',
                mock.ANY,
                'org.freedesktop.login1.Session',
                mock.ANY
        )

        self._manager.call_sync.assert_called_with(
                'ListSessions',
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY
        )

        if check_all_sessions:
            for session_id, session in self._sessions.items():
                try:
                    session.get_cached_property.assert_called()
                except AssertionError as e:
                    raise AssertionError('Session ID {}'.format(session_id)) from e

    @contextmanager
    def patch(self, target: str, check_all_sessions: bool = False):
        """Convenience patch wrapper for MockGio, with assertions

        As with mock.patch normally, the "target" is the fully-qualified
        attribute name of the "Gio" object which should be replaced by this
        MockGio. See also:
        https://docs.python.org/3.6/library/unittest.mock.html#where-to-patch
        """

        with mock.patch(target, new=self) as mock_gio:
            yield mock_gio
            mock_gio.assert_fully_exercised(check_all_sessions)
