"""Interact with TTY/PTY devices in /dev"""


import datetime
import os
import re
from typing import Tuple

from .exception import SessionParseError


class TTY:
    """Representation of the TTY assigned to a given Session"""

    # The access time of the TTY/PTY, which is updated only by user activity
    # (and, occasionally, by stop-idle-sessions!)
    _atime: datetime.datetime

    # The modification time of the TTY/PTY, which is updated by both user
    # activity and stdout/stderr from programs
    _mtime: datetime.datetime

    def __init__(self, name: str):
        if re.match(r'^(tty|pts/)[0-9]+$', name):
            self._name = name
            self._atime, self._mtime = TTY._os_initialize_times(self.full_name)
        else:
            raise SessionParseError(f'invalid shortname for tty/pts: {name}')

    def __eq__(self, other):
        return TTY.compare(self, other)

    @staticmethod
    def compare(me, other) -> bool:
        """Duck-type comparison of two objects claiming to be TTYs"""

        if (not hasattr(me, 'name') or
            not hasattr(other, 'name') or
            me.name != other.name):
            return False

        if (not hasattr(me, 'full_name') or
            not hasattr(other, 'full_name') or
            me.full_name != other.full_name):
            return False

        if (not hasattr(me, 'atime') or
            not hasattr(other, 'atime') or
            me.atime != other.atime):
            return False

        if (not hasattr(me, 'mtime') or
            not hasattr(other, 'mtime') or
            me.mtime != other.mtime):
            return False

        return True

    @property
    def name(self) -> str:
        """Short name of the TTY (e.g., 'pts/4')"""
        return self._name

    @property
    def full_name(self) -> str:
        """Just prepend /dev/ onto name"""
        return "/dev/" + self.name

    @property
    def atime(self) -> datetime.datetime:
        """Access time, which is updated by user activity only"""
        return self._atime

    @property
    def mtime(self) -> datetime.datetime:
        """Modification time, which is updated by user activity AND stdout"""
        return self._mtime

    def touch_times(self, timestamp: datetime.datetime):
        """Modify the filesystem entry for the TTY to set its atime to timestamp
  
        Update the atime and mtime of the TTY/PTY at the full_name path to
        match the provided timestamp.
        """
        TTY._os_touch_times(self.full_name, timestamp, timestamp)
        self._atime, self._mtime = timestamp, timestamp

    @staticmethod
    def _os_initialize_times(path: str) -> Tuple[datetime.datetime,
                                                 datetime.datetime]:
        """As a staticmethod, this can easily be mocked"""
        try:
            st_result = os.stat(path)
            return (datetime.datetime.fromtimestamp(st_result.st_atime),
                    datetime.datetime.fromtimestamp(st_result.st_mtime))
        except OSError as err:
            raise SessionParseError(f'Failed to stat {path}') from err


    @staticmethod
    def _os_touch_times(path: str,
                        atime: datetime.datetime,
                        mtime: datetime.datetime):
        """As a staticmethod, this can easily be mocked"""
        try:
            os.utime(path, times=(atime.timestamp(),
                                mtime.timestamp()))
        except OSError as err:
            raise SessionParseError(f'Failed to touch {path}') from err
