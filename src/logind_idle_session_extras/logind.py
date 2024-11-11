"""Session information from systemd-logind"""


from enum import auto, Enum
from typing import Collection

from gi.repository import Gio


class SessionType(Enum):
    """Distinguish between several meaningful categories of Session"""
    LOCAL = auto()
    SSH = auto()
    VNC = auto()
    OTHER = auto()


class Session:
    """Proxy for the org.freedesktop.login1.Session interface

    This is a representation of a single session object as maintained by the
    systemd-logind service. Do not attempt to create this object directly, but
    instead use the Manager class to query for Session object(s).
    """

    _manager = None
    _session: Gio.DBusProxy

    @classmethod
    def initialize_from_manager(cls,
                                manager,
                                bus: Gio.DBusConnection,
                                session_id: str):
        node_name = '/org/freedesktop/login1/session/{}'.format(session_id)
        self = cls()
        self._manager = manager
        self._session = Gio.DBusProxy.new_sync(bus,
                                               Gio.DBusProxyFlags.NONE,
                                               None,
                                               'org.freedesktop.login1',
                                               node_name,
                                               'org.freedesktop.login1.Session',
                                               None)
        return self

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
        id = self._session.get_cached_property('Id')
        if id is None:
            raise ValueError('Could not retrieve session Id')
        return id.get_string()

    @property
    def session_type(self) -> SessionType:
        """One of several meaningful categories for this Session"""
        if self._session.get_cached_property('Type') == 'tty':
            # TODO: need to check whether it is local
            return SessionType.SSH
        else:
            return SessionType.OTHER


class Manager:
    """Proxy for the org.freedesktop.login1.Manager interface

    This represents the API for the systemd-logind service, which is exposed
    by D-Bus and which can be used to query (and possibly modify) the state of
    login sessions system-wide. Use an instance of this class to query and
    introspect this global state.
    """

    _bus: Gio.DBusConnection
    _manager: Gio.DBusProxy

    def __init__(self):
        self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._manager = Gio.DBusProxy.new_sync(self._bus,
                                               Gio.DBusProxyFlags.NONE,
                                               None,
                                               'org.freedesktop.login1',
                                               '/org/freedesktop/login1',
                                               'org.freedesktop.login1.Manager',
                                               None)

    def get_all_sessions(self) -> Collection[Session]:
        """Obtain objects for each Session that currently exists"""
        sessions: Collection[Session] = []
        for raw_session in self._manager.call_sync('ListSessions',
                                                   None,
                                                   Gio.DBusCallFlags.NONE,
                                                   -1,
                                                   None).unpack()[0]:
            session_id = raw_session[0]
            sessions.append(Session.initialize_from_manager(self,
                                                            self._bus,
                                                            session_id))
        return sessions
