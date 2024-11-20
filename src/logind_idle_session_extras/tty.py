"""Interact with TTY/PTY devices in /dev"""


import datetime
import os
import re
from typing import Tuple


class TTY:
    """Representation of the TTY assigned to a given Session"""

    # The access time of the TTY/PTY, which is updated only by user activity
    # (and, occasionally, by logind-idle-session-extras!)
    _atime: datetime.datetime

    # The modification time of the TTY/PTY, which is updated by both user
    # activity and stdout/stderr from programs
    _mtime: datetime.datetime

    def __init__(self, name: str):
        if re.match(r'^(tty|pts/)[0-9]+$', name):
            self._name = name
            self._atime, self._mtime = self._initialize_times()
        else:
            raise ValueError('invalid shortname for tty/pts: {}'.format(name))

    @property
    def name(self) -> str:
        return self._name

    @property
    def full_name(self) -> str:
        """Just prepend /dev/ onto name"""
        return "/dev/" + self.name

    @property
    def atime(self) -> datetime.datetime:
        return self._atime

    @property
    def mtime(self) -> datetime.datetime:
        return self._mtime

    def _initialize_times(self) -> Tuple[datetime.datetime, datetime.datetime]:
        st_result = os.stat(self.full_name)
        return (datetime.datetime.fromtimestamp(st_result.st_atime),
                datetime.datetime.fromtimestamp(st_result.st_mtime))

    def _os_touch_times(self,
                        atime: datetime.datetime,
                        mtime: datetime.datetime):
        os.utime(self.full_name,
                 times=(timestamp.timestamp(),
                        timestamp.timestamp()))

    def touch_times(self, timestamp: datetime.datetime):
        """Modify the filesystem entry for the TTY to set its atime to timestamp
  
        Update the atime and mtime of the TTY/PTY at the full_name path to
        match the provided timestamp.
        """
        self._os_touch_times(timestamp, timestamp)
        self._atime, self._mtime = timestamp, timestamp
