"""Process table information, including /sys/fs/cgroup"""


import re
from typing import Callable, List, Mapping, NamedTuple

import psutil

from .exception import SessionParseError


class Process(NamedTuple):
    """Representation of a process either inside of a Session or otherwise"""

    # Process identifier (PID) of this process
    pid: int

    # The full command line that the process is running with
    cmdline: str

    # A mapping of environment variable names to values
    environ: Mapping[str, str]

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
                processes.append(Process(
                        pid=ps_obj.pid,
                        cmdline=cmdline,
                        environ=ps_obj.environ()
                ))
        return processes
    except OSError as err:
        raise SessionParseError(f"Could not read cgroup pids for "
                                f"scope {scope_path}") from err
