"""X11 screen saver information to determine idle time"""


import os
import re
import shutil
import tempfile
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

    try:
        if xauthority is not None:
            with tempfile.NamedTemporaryFile() as temp_xauth:
                with open(xauthority, 'rb') as orig_xauth:
                    shutil.copyfileobj(orig_xauth,
                                       temp_xauth)
                    temp_xauth.seek(0)

                    os.environ['XAUTHORITY'] = temp_xauth.name

                    d = Xlib.display.Display(display)
                    return d.screen().root.screensaver_query_info().idle

        else:
            d = Xlib.display.Display(display)
            return d.screen().root.screensaver_query_info().idle

    except Xlib.error.DisplayConnectionError as err:
        raise SessionParseError(f'Could not connect to X11 display identified '
                                f'by "{display}"') from err
    except OSError as err:
        raise SessionParseError(f'Could not borrow Xauthority from '
                                f'{xauthority} for display {display}') from err
