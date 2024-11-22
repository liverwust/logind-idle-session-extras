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
        xvnc_match = X11SessionProcesses.parse_xvnc_cmdline(process.cmdline)

        display: Optional[str] = None
        xauthority: Optional[str] = None

        if xvnc_match[0] is not None:
            display = xvnc_match[0]
        elif 'DISPLAY' in process.environ:
            display = process.environ['DISPLAY']

        if xvnc_match[1] is not None:
            xauthority = xvnc_match[1]
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

    @staticmethod
    def parse_xvnc_cmdline(cmdline: str) -> Tuple[Optional[str],
                                                  Optional[str]]:
        """Attempt to identify information from an Xvnc command line

        The first element of the returned tuple is a candidate DISPLAY, if one
        is found. The second is a candidate XAUTHORITY, if one is found.
        """

        xvnc_re = re.compile(r'^.*Xvnc\s+(:[0-9]+).*-auth\s+(\S+).*$')

        xvnc_match = xvnc_re.match(cmdline)
        if xvnc_match is not None:
            return (xvnc_match.group(1), xvnc_match.group(2))

        return (None, None)

    @staticmethod
    def retrieve_idle_time_ms(display: str,
                              xauthority: Optional[str] = None) -> timedelta:
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
            idle_time_ms = d.screen().root.screensaver_query_info().idle
            return timedelta(milliseconds=idle_time_ms)

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
