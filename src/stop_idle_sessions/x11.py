"""X11 screen saver information to determine idle time"""


from collections import defaultdict
from datetime import timedelta
import os
import re
from typing import List, Mapping, Optional, Set, Tuple

import Xlib.display
import Xlib.error

from .exception import SessionParseError
from .ps import Process


class X11SessionProcesses:
    """Collect related Process objects and use them to determine X11 params

    There are often many Process objects associated with a SystemD scope or
    session. There may be one (or more!) instances of the DISPLAY or
    XAUTHORITY variables among them. Some of their commandlines may even
    provide clues as to these parameters.

    Once collected, these parameters can point to one or more DISPLAYs which
    may provide an idle time (via the X11 Screen Saver extension).
    """

    def __init__(self):
        # Each "candidate tuple" associates a DISPLAY environment variable (or
        # parsed command-line value) with an XAUTHORITY environment variable
        # (or parsed command-line value). XAUTHORITY may be absent.
        self._candidate_tuples: List[Tuple[str, Optional[str]]] = []

    def add(self, process: Process):
        """Add information from a Process to the internal tracking list

        This will extract information from the given Process which will allow
        the "candidate tuples" list to expand and incorporate the new info.
        The Processes are not actually collected internally per se -- just
        relevant information.
        """

        # Try some specific command lines
        xserver_match = X11SessionProcesses.parse_xserver_cmdline(process.cmdline)

        display: Optional[str] = None
        xauthority: Optional[str] = None

        if xserver_match[0] is not None:
            display = xserver_match[0]
        elif 'DISPLAY' in process.environ:
            display = process.environ['DISPLAY']

        if xserver_match[1] is not None:
            xauthority = xserver_match[1]
        elif 'XAUTHORITY' in process.environ:
            xauthority = process.environ['XAUTHORITY']

        if display is not None:
            self._candidate_tuples.append((display, xauthority))

    def get_all_candidates(self) -> List[Tuple[str, Optional[str]]]:
        """Review each of the candidates tuples for DISPLAY/XAUTHORITY pairs

        Every DISPLAY can be tried without any XAUTHORITY. If a given
        XAUTHORITY shows up for a DISPLAY, then return it as a candidate.
        """

        display_xauthorities: Mapping[str,
                                      Set[Optional[str]]] = defaultdict(set)

        for display, xauthority in self._candidate_tuples:
            display_xauthorities[display].add(xauthority)

        # Make sure that we try XAUTHORITY = None for each of these
        for xauthority_set in display_xauthorities.values():
            if None not in xauthority_set:
                xauthority_set.add(None)

        resulting_list: List[Tuple[str, Optional[str]]] = []
        for display, xauthority_set in display_xauthorities.items():
            for xauthority in xauthority_set:
                resulting_list.append((display, xauthority))

        return resulting_list

    def retrieve_least_display_idletime(self) -> Optional[Tuple[str,
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

        for display, xauthority in self.get_all_candidates():
            try:
                candidate_idletime = X11SessionProcesses.retrieve_idle_time(
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
