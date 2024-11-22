"""Session information from systemd-logind"""


from typing import List

from gi.repository import Gio, GLib

from .exception import SessionParseError


class Session:
    """Proxy for the org.freedesktop.login1.Session interface

    This is a representation of a single session object as maintained by the
    systemd-logind service. Do not attempt to create this object directly, but
    instead use the get_all_sessions function to query for these.
    """

    _session: Gio.DBusProxy

    @classmethod
    def initialize_from_manager(cls,
                                bus: Gio.DBusConnection,
                                session_id: str):
        """Entry point for Manager -- do not call this directly"""
        node_name = f'/org/freedesktop/login1/session/{session_id}'
        self = cls()
        try:
            self._session = Gio.DBusProxy.new_sync(bus,
                                                Gio.DBusProxyFlags.NONE,
                                                None,
                                                'org.freedesktop.login1',
                                                node_name,
                                                'org.freedesktop.login1.Session',
                                                None)
            return self
        except GLib.Error as err:
            raise SessionParseError(f'Problem fetching session id '
                                    f'{session_id}: {err.message}') from err

    def __eq__(self, other):
        """Two Sessions are equal if they share the same ID"""
        if isinstance(other, Session):
            return self.session_id == other.session_id
        return False

    def __hash__(self):
        """Two Sessions are equal if they share the same ID"""
        return hash(self.session_id)

    @property
    def session_id(self) -> str:
        """Unique identifier for the Session"""
        session_id = self._session.get_cached_property('Id')
        if session_id is None:
            raise ValueError('Could not retrieve session Id')
        return session_id.get_string()

    @property
    def uid(self) -> int:
        """User identifier (UID) for this Session"""
        uid = self._session.get_cached_property('User')
        if uid is None:
            raise ValueError('Could not retrieve session UID')
        return uid.unpack()[0]

    @property
    def tty(self) -> str:
        """TTY or PTY for this Session (or a blank string)"""
        tty = self._session.get_cached_property('TTY')
        if tty is None:
            raise ValueError('Could not retrieve session TTY')
        return tty.get_string()

    @property
    def leader(self) -> int:
        """PID of the process that registered the session"""
        leader = self._session.get_cached_property('Leader')
        if leader is None:
            raise ValueError('Could not retrieve session Leader')
        return leader.get_uint32()

    @property
    def scope(self) -> str:
        """Systemd scope name for this Session"""
        scope = self._session.get_cached_property('Scope')
        if scope is None:
            raise ValueError('Could not retrieve session Scope')
        return scope.get_string()

    @property
    def scope_path(self) -> str:
        """'Fully-qualified' SystemD scope path for this Session"""
        return f"/user.slice/user-{self.uid}.slice/{self.scope}"


def get_all_sessions() -> List[Session]:
    """Proxy for the org.freedesktop.login1.Manager interface

    This represents the API for the systemd-logind service, which is exposed
    by D-Bus and which can be used to query (and possibly modify) the state of
    login sessions system-wide. Use an instance of this class to query and
    introspect this global state.
    """

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        manager = Gio.DBusProxy.new_sync(bus,
                                        Gio.DBusProxyFlags.NONE,
                                        None,
                                        'org.freedesktop.login1',
                                        '/org/freedesktop/login1',
                                        'org.freedesktop.login1.Manager',
                                        None)

        sessions: List[Session] = []
        for raw_session in manager.call_sync('ListSessions',
                                            None,
                                            Gio.DBusCallFlags.NONE,
                                            -1,
                                            None).unpack()[0]:
            session_id = raw_session[0]
            sessions.append(Session.initialize_from_manager(bus, session_id))
        return sessions
    except GLib.Error as err:
        raise SessionParseError(f'Problem fetching all sessions from bus: '
                                f'{err.message}') from err
