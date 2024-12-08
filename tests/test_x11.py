"""Unit testing for the X11 logic"""


from unittest import TestCase

from stop_idle_sessions.ps import Process
from stop_idle_sessions.x11 import X11DisplayCollector


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

        actual_results = X11DisplayCollector.parse_xserver_cmdline(
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

        actual_results = X11DisplayCollector.parse_xserver_cmdline(
                sample_cmdline
        )

        self.assertEqual(expected_results, actual_results)


class X11DisplayCollectorTestCase(TestCase):
    """Verify correct accumulation and handling of process information"""

    def test_normal_collection_of_vnc_processes(self):
        """This is a common case where a few VNC processes share a DISPLAY"""

        bag = X11DisplayCollector()
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

        # Reach directly into the object for now
        # pylint: disable=protected-access
        self.assertDictEqual(bag._session_displays,
                             {'session_id': set([':1'])})
        self.assertDictEqual(bag._display_xauthorities,
                             {':1': set([None, '/home/auser/.Xauthority'])})
