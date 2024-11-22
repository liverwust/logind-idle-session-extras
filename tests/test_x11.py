"""Unit testing for the X11 logic"""


from unittest import TestCase

import stop_idle_sessions.x11


class ParseXauthorityTestCase(TestCase):
    """Verify the behavior of the xauth command line parser"""

    def test_parse_xauthority_cmdline(self):
        """Verify the behavior of the xauth command line parser"""

        sample_cmdline = "/usr/bin/Xvnc :1 -auth /home/louis/.Xauthority -desktop samplehost.sampledomain:1 (auser) -fp catalogue:/etc/X11/fontpath.d -geometry 1024x768 -pn -rfbauth /home/auser/.vnc/passwd -rfbport 5901 -localhost"
        expected_xauthority = '/home/louis/.Xauthority'

        actual_xauthority = stop_idle_sessions.x11.parse_xauthority_cmdline(
                sample_cmdline
        )

        self.assertEqual(expected_xauthority, actual_xauthority)
