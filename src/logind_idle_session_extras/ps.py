"""Process table information, including /sys/fs/cgroup"""


import re
from typing import Collection

import psutil


def processes_in_scope_path(scope_path: str) -> Collection[psutil.Process]:
    """Obtain the set of PIDs for a given fully-qualified scope path"""

    if not re.match(r'^\/user\.slice\/user-\d+\.slice\/[^.\/]+\.scope$', scope_path):
        raise ValueError('invalid fully-qualified scope path: {}'.format(scope_path))

    processes: Collection[psutil.Process] = []
    with open("/sys/fs/cgroup{}/cgroup.procs".format(scope_path), "r") as cgroup_f:
        for cgroup_line in cgroup_f:
            pid = int(cgroup_line)
            processes.append(psutil.Process(pid))
    return processes
