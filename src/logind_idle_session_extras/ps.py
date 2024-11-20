"""Process table information, including /sys/fs/cgroup"""


import re
from typing import Callable, List, NamedTuple

import psutil


class Process(NamedTuple):
    """Representation of a process either inside of a Session or otherwise"""

    # Process identifier (PID) of this process
    pid: int

    # Short name of the binary image (e.g., "sshd") for this process
    comm: str

    # The full command line that the process is running with
    cmdline: str

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
    with open_func(f"/sys/fs/cgroup/systemd{scope_path}/cgroup.procs",
                   "r") as cgroup_f:
        for cgroup_line in cgroup_f.readlines():
            pid = int(cgroup_line)
            ps_obj = psutil.Process(pid)
            processes.append(Process(
                    pid=ps_obj.pid,
                    comm=ps_obj.name(),
                    cmdline=' '.join(ps_obj.cmdline())
            ))
    return processes
