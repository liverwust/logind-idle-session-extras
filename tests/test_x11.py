"""Unit testing for the X11 logic"""


from datetime import timedelta
from typing import Mapping, Optional, Tuple
from unittest import TestCase
from unittest.mock import Mock, patch

from stop_idle_sessions.ps import Process
import stop_idle_sessions.x11


class ParseCommandLineTestCase(TestCase):
    """Verify the behavior of the DISPLAY/XAUTHORITY command line parser"""

    def test_parse_xvnc_cmdline(self):
        """Verify the behavior of the Xvnc command line parser"""

        sample_cmdline = ("/usr/bin/Xvnc :1 -auth /home/auser/.Xauthority "
                          "-desktop samplehost.sampledomain:1 (auser) -fp "
                          "catalogue:/etc/X11/fontpath.d -geometry 1024x768 "
                          "-pn -rfbauth /home/auser/.vnc/passwd -rfbport 5901"
                          "-localhost")
        expected_results = (':1', '/home/auser/.Xauthority')

        actual_results = stop_idle_sessions.x11.X11DisplayCollector.parse_xserver_cmdline(
                sample_cmdline
        )

        self.assertEqual(expected_results, actual_results)

    def test_parse_xwayland_cmdline(self):
        """Verify the behavior of the Xwayland command line parser"""

        sample_cmdline = ("/usr/bin/Xwayland :1024 -rootless -terminate "
                          "-accessx -core -auth "
                          "/run/user/42/.mutter-Xwaylandauth.8ZZMX2 "
                          "-listen 4 -listen 5 -displayfd 6")
        expected_results = (':1024', '/run/user/42/.mutter-Xwaylandauth.8ZZMX2')

        actual_results = stop_idle_sessions.x11.X11DisplayCollector.parse_xserver_cmdline(
                sample_cmdline
        )

        self.assertEqual(expected_results, actual_results)


class X11DisplayCollectorTestCase(TestCase):
    """Verify correct accumulation and handling of process information"""

    @staticmethod
    def mock_retrieve_idle_time(display: str,
                                xauthority: Optional[str]) -> Optional[timedelta]:
        """Mock implementation of X11DisplayCollector.retrieve_idle_time"""
        lookup_table: Mapping[Tuple[str, Optional[str]], Optional[timedelta]] = {
                (':1', '/home/auser/.Xauthority'): timedelta(seconds=1200),
                (':1', None): None,
                (':2', None): None
        }
        return lookup_table[(display, xauthority)]

    def setUp(self):
        self._mocked_retrieve_idle_time = Mock(
                side_effect=X11DisplayCollectorTestCase.mock_retrieve_idle_time
        )
        retrieve_idle_time_patcher = patch(
                'stop_idle_sessions.x11.X11DisplayCollector.retrieve_idle_time',
                self._mocked_retrieve_idle_time
        )
        retrieve_idle_time_patcher.start()
        self.addCleanup(retrieve_idle_time_patcher.stop)

    def test_normal_collection_of_vnc_processes(self):
        """This is a common case where a few VNC processes share a DISPLAY"""

        bag = stop_idle_sessions.x11.X11DisplayCollector()
        processes = [
            Process(
                    pid=20272,
                    cmdline=('/usr/bin/Xvnc :1 -auth /home/auser/.Xauthority '
                             '-desktop remotehost.remotedomain (auser) -fp '
                             'catalogue:/etc/X11/fontpath.d -geometry 1024x768 '
                             '-pn -rfbauth /home/auser/.vnc/passwd -rfbport '
                             '5901 -localhost'),
                    environ={}
            ),
            Process(
                    pid=20277,
                    cmdline='/bin/sh /home/auser/.vnc/xstartup',
                    environ={
                        'DISPLAY': ':1'
                    }
            ),
            Process(
                    pid=20278,
                    cmdline='/usr/libexec/gnome-session-binary',
                    environ={
                        'DISPLAY': ':1'
                    }
            ),
            Process(
                    pid=20373,
                    cmdline='/usr/bin/gnome-shell',
                    environ={
                        'DISPLAY': ':1'
                    }
            )
        ]

        for process in processes:
            bag.add('session_id', process)

        self.assertEqual(
                bag.retrieve_least_display_idletime('session_id'),
                (':1', timedelta(seconds=1200))
        )

        self._mocked_retrieve_idle_time.assert_called_once_with(
                ':1', '/home/auser/.Xauthority'
        )

    def test_display_only_no_xauthority(self):
        """This is where sshd has a DISPLAY but advertises no XAUTHORITY

        The intention is to simulate the following scenario:
          1) User has set up an SSH session with `ssh -X` (X11Forwarding).
          2) stop-idle-sessions sees this information available but does not
             retrieve xauthority information.
          3) "X11 connection rejected because of wrong authentication."
             message is displayed on the user's console.

        For now, disregard any DISPLAY for a Session if it does not have a
        discernable XAUTHORITY. This may be undesirable in the long-run --
        i.e., it might be better to detect this _specific_ condition rather
        than disregarding all unauthenticated X11 -- but it will fix the issue
        for now.
        """

        bag = stop_idle_sessions.x11.X11DisplayCollector()
        processes = [
            Process(
                    pid=20272,
                    cmdline='sshd: auser [priv]',
                    environ={}
            ),
            Process(
                    pid=20277,
                    cmdline='sshd: auser@pts/2',
                    environ={}
            ),
            Process(
                    pid=20278,
                    cmdline='-zsh',
                    environ={
                        'DISPLAY': ':2'
                    }
            )
        ]

        for process in processes:
            bag.add('session_id', process)

        self.assertEqual(
                bag.retrieve_least_display_idletime('session_id'),
                None
        )

        self._mocked_retrieve_idle_time.assert_not_called()
