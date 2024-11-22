"""Process table information, including /sys/fs/cgroup"""


import re
from typing import Callable, List, NamedTuple, Optional

import psutil

from .exception import SessionParseError
from .x11 import parse_xauthority_cmdline


class Process(NamedTuple):
    """Representation of a process either inside of a Session or otherwise"""

    # Process identifier (PID) of this process
    pid: int

    # The full command line that the process is running with
    cmdline: str

    # The value of the DISPLAY environment variable, if present (or None)
    display: Optional[str]

    # The value of the XAUTHORITY environment variable, if present (or None)
    xauthority: Optional[str]

    def __eq__(self, other):
        if isinstance(other, Process):
            return self.pid == other.pid
        return False


def processes_in_scope_path(scope_path: str,
                            open_func: Callable = open) -> List[Process]:
    """Obtain the set of PIDs for a given fully-qualified scope path"""

    if not re.match(r'^\/user\.slice\/user-\d+\.slice\/[^.\/]+\.scope$', scope_path):
        raise ValueError(f'invalid fully-qualified scope path: {scope_path}')

    processes: List[Process] = []

    try:
        with open_func(f"/sys/fs/cgroup/systemd{scope_path}/cgroup.procs",
                    "r") as cgroup_f:
            for cgroup_line in cgroup_f.readlines():
                pid = int(cgroup_line)
                ps_obj = psutil.Process(pid)
                cmdline = ' '.join(ps_obj.cmdline())

                display: Optional[str] = None
                xauthority: Optional[str] = None
                if 'DISPLAY' in ps_obj.environ():
                    display = ps_obj.environ()['DISPLAY']
                if 'XAUTHORITY' in ps_obj.environ():
                    xauthority = ps_obj.environ()['XAUTHORITY']

                # This is a special case -- some X11-related apps specify
                # -auth on their cmdlines
                cmdline_xauthority_override = parse_xauthority_cmdline(cmdline)
                if cmdline_xauthority_override is not None:
                    xauthority = cmdline_xauthority_override

                processes.append(Process(
                        pid=ps_obj.pid,
                        cmdline=cmdline,
                        display=display,
                        xauthority=xauthority
                ))
        return processes
    except OSError as err:
        raise SessionParseError(f"Could not read cgroup pids for "
                                f"scope {scope_path}") from err
