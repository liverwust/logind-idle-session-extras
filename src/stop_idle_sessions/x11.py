"""X11 screen saver information to determine idle time"""


from collections import defaultdict
from datetime import timedelta
import os
import re
from typing import Dict, Optional, Set, Tuple

import Xlib.display
import Xlib.error

from .exception import SessionParseError
from .ps import Process


class X11DisplayCollector:
    """Collect related Process objects to determine X11 params across sessions

    There are often many Process objects associated with a SystemD scope or
    session. There may be one (or more!) instances of the DISPLAY or
    XAUTHORITY variables among them. Some of their commandlines may even
    provide clues as to these parameters.

    In some cases, such as for x11vnc, the full picture may not emerge until
    _multiple_ sessions have been processed. For this reason, the
    X11DisplayCollector is intended to provide a global repository that all
    session processes are fed into. It can then provide back an iteration of
    identified displays associated with each session.

    Once collected, these parameters can point to one or more DISPLAYs which
    may provide an idle time (via the X11 Screen Saver extension).
    """

    def __init__(self):
        # Each session identifier string may be associated with one or more
        # individual DISPLAY candidates.
        self._session_displays: Dict[str, Set[str]] = defaultdict(set)

        # Subsequently, each individual DISPLAY can be associated with one or
        # more individual XAUTHORITY candidates.
        self._display_xauthorities: Dict[str, Set[str]] = defaultdict(set)

    def add(self, session: str, process: Process):
        """Add information from a Process and its session ID to tracking

        This will extract information from the given Process which will allow
        the "candidate tuples" list to expand and incorporate the new info.
        The Processes are not actually collected internally per se -- just
        relevant information.
        """

        # Try some specific command lines
        xserver_match = X11DisplayCollector.parse_xserver_cmdline(process.cmdline)
        x11vnc_match = X11DisplayCollector.parse_x11vnc_cmdline(process.cmdline)

        display: Optional[str] = None
        xauthority: Optional[str] = None

        if xserver_match[0] is not None:
            display = xserver_match[0]
        elif x11vnc_match is not None:
            display = x11vnc_match
        elif 'DISPLAY' in process.environ:
            display = process.environ['DISPLAY']

        if xserver_match[1] is not None:
            xauthority = xserver_match[1]
        elif 'XAUTHORITY' in process.environ:
            xauthority = process.environ['XAUTHORITY']

        if display is not None:
            self._session_displays[session].add(display)
            if xauthority is not None:
                self._display_xauthorities[display].add(xauthority)

    def retrieve_least_display_idletime(self, session: str) -> Optional[Tuple[str,
                                                                        timedelta]]:
        """Retrieve the smallest of DISPLAY idletimes, and the DISPLAY itself

        Why the smallest? We want to be as optimistic as possible about idle
        times to keep from terminating user processes without a good reason.
        Even if there is, say, a rogue process in a VNC session which is
        connected to some external place via X11 forwarding, we would rather
        that idletime be checked against both (perhaps surprisingly) than to
        incorrectly terminate a non-idle session.

        The first return value is the DISPLAY string, and the second is its
        idletime.
        """

        # Arbitrarily keep track of one (of possibly several)
        # SessionParseErrors, and raise it if no timedeltas are ever
        # successfully retrieved.
        any_exception: Optional[SessionParseError] = None
        result: Optional[Tuple[str, timedelta]] = None

        for display in self._session_displays[session]:
            for xauthority in self._display_xauthorities[display]:
                try:
                    candidate_idletime = X11DisplayCollector.retrieve_idle_time(
                            display,
                            xauthority
                    )
                    if candidate_idletime is not None:
                        if result is None:
                            result = (display, candidate_idletime)
                        elif candidate_idletime < result[1]:
                            result = (display, candidate_idletime)

                except SessionParseError as err:
                    # Given the choice: If an XAUTHORITY was determined, then
                    # trust the _new_ error. If no XAUTHORITY was determined, then
                    # keep the _old_ error (because it is very likely that a None
                    # XAUTHORITY would fail normally).
                    if any_exception is None or xauthority is not None:
                        any_exception = err

        if result is not None:
            return result
        if any_exception is not None:
            raise any_exception
        return None

    @staticmethod
    def parse_xserver_cmdline(cmdline: str) -> Tuple[Optional[str],
                                                     Optional[str]]:
        """Attempt to identify information from an X command line

        The first element of the returned tuple is a candidate DISPLAY, if one
        is found. The second is a candidate XAUTHORITY, if one is found.
        This works with Xvnc, Xwayland, and possibly others.
        """

        xserver_re = re.compile(r'^.*X[a-z]+\s+(:[0-9]+).*-auth\s+(\S+).*$')

        xserver_match = xserver_re.match(cmdline)
        if xserver_match is not None:
            return (xserver_match.group(1), xserver_match.group(2))

        return (None, None)

    @staticmethod
    def parse_x11vnc_cmdline(cmdline: str) -> Optional[str]:
        """Attempt to identify information from an x11vnc command line

        Similar to an X server, it may be possible to obtain information from
        an x11vnc command line. This is a little different because it can't
        usually provide XAUTHORITY information, but only XDISPLAY information.
        """

        x11vnc_re = re.compile(r'^.*x11vnc.*-display\s+(:[0-9]+).*$')

        x11vnc_match = x11vnc_re.match(cmdline)
        if x11vnc_match is not None:
            return x11vnc_match.group(1)

        return None

    @staticmethod
    def retrieve_idle_time(display: str,
                           xauthority: Optional[str] = None) -> Optional[timedelta]:
        """Retrieve the idle time (in milliseconds) for the given X11 DISPLAY"""

        # Crazy hack to try and work around this issue, reported by a _different
        # project_ (which has never made it into the python-xlib upstream):
        # https://github.com/asweigart/pyautogui/issues/202
        extensions = getattr(Xlib.display, 'ext').__extensions__
        if ('RANDR', 'randr') in extensions:
            extensions.remove(('RANDR', 'randr'))
        if ('XFIXES', 'xfixes') in extensions:
            extensions.remove(('XFIXES', 'xfixes'))

        try:
            if xauthority is not None:
                os.environ['XAUTHORITY'] = xauthority

            d = Xlib.display.Display(display)
            if d.has_extension('MIT-SCREEN-SAVER'):
                idle_time_ms = d.screen().root.screensaver_query_info().idle
                return timedelta(milliseconds=idle_time_ms)

            # The DISPLAY doesn't support the screen saver extension, which
            # means it is probably either forwarded (X11) or running a GDM
            # login session.
            return None

        except Xlib.error.DisplayConnectionError as err:
            raise SessionParseError(f'Could not connect to X11 display identified '
                                    f'by "{display}"') from err

        except Xlib.error.ConnectionClosedError as err:
            raise SessionParseError(f'Could not maintain a connection to the X11 '
                                    f'display identified by "{display}"') from err

        except AttributeError as err:
            raise SessionParseError(f'Cannot access attributes from X11 server '
                                    f'responses associated with display '
                                    f'"{display}", probably due to a broken or '
                                    f'erroneous connection') from err
