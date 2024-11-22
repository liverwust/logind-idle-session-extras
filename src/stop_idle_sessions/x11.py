"""X11 screen saver information to determine idle time"""


import os
import re
from typing import Optional

import Xlib.display
import Xlib.error

from .exception import SessionParseError


def parse_xauthority_cmdline(cmdline: str) -> Optional[str]:
    """Attempt to identify an XAUTHORITY from the cmdline"""

    xvnc_auth_re = re.compile(r'^.*Xvnc.*-auth\s+(\S+).*$')

    xvnc_auth_match = xvnc_auth_re.match(cmdline)
    if xvnc_auth_match is not None:
        return xvnc_auth_match.group(1)

    return None

def retrieve_idle_time_ms(display: str,
                          xauthority: Optional[str] = None) -> int:
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
        return d.screen().root.screensaver_query_info().idle

    except Xlib.error.DisplayConnectionError as err:
        raise SessionParseError(f'Could not connect to X11 display identified '
                                f'by "{display}"') from err

    except Xlib.error.ConnectionClosedError as err:
        raise SessionParseError(f'Could not maintain a connection to the X11 '
                                f'display identified by "{display}"') from err
