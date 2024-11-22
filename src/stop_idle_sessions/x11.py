"""X11 screen saver information to determine idle time"""


import Xlib.display
import Xlib.error

from .exception import SessionParseError


def retrieve_idle_time_ms(display: str) -> int:
    """Retrieve the idle time (in milliseconds) for the given X11 DISPLAY"""

    try:
        d = Xlib.display.Display(display)
        return d.screen().root.screensaver_query_info().idle
    except Xlib.error.DisplayConnectionError as err:
        raise SessionParseError(f'Could not connect to X11 display identified '
                                f'by "{display}"') from err
