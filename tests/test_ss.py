"""Unit testing for the ss module"""


from contextlib import contextmanager
from ipaddress import ip_address
from os.path import basename
from textwrap import dedent
from unittest import TestCase
from unittest.mock import Mock, patch

from logind_idle_session_extras import ss


def _subprocess_run_checker(output: str):
    """Validate the subprocess.run input and return output if OK"""

    def _inner_subprocess_run_checker(*args, **_):
        if basename(args[0][0]) != "ss":
            raise ValueError("Unexpected command {}".format(args[0]))
        completedProcess = Mock()
        completedProcess.stdout = output
        return completedProcess

    return _inner_subprocess_run_checker


@contextmanager
def patch_subprocess_run(target: str, output: str):
    """Patch the subprocess.run method to return some output

    As with mock.patch normally, the "target" is the fully-qualified attribute
    name of the "subprocess.run" object which should be replaced by this
    mocked version. See also:
    https://docs.python.org/3.6/library/unittest.mock.html#where-to-patch
    """

    mock_run = Mock(side_effect=_subprocess_run_checker(output))
    with patch(target, new=mock_run) as mock_run:
        yield mock_run
        mock_run.assert_called_once()


class TwoVncConnectionTestCase(TestCase):
    """Dummy output and a nominal test case showing two VNC connections"""

    @staticmethod
    def command_output() -> str:
        return dedent("""\
            LISTEN    0      100         127.0.0.1:25           0.0.0.0:*     users:(("master",pid=5337,fd=14))                          
            LISTEN    0      5           127.0.0.1:5901         0.0.0.0:*     users:(("Xvnc",pid=952570,fd=6))                           
            LISTEN    0      5           127.0.0.1:5902         0.0.0.0:*     users:(("Xvnc",pid=1258996,fd=6))                          
            LISTEN    0      128           0.0.0.0:111          0.0.0.0:*     users:(("rpcbind",pid=4410,fd=4),("systemd",pid=1,fd=42))  
            LISTEN    0      128           0.0.0.0:22           0.0.0.0:*     users:(("sshd",pid=4960,fd=3))                             
            LISTEN    0      2048        127.0.0.1:631          0.0.0.0:*     users:(("cupsd",pid=162159,fd=8))                          
            ESTAB     0      452        10.0.0.169:22        10.0.3.209:57343 users:(("sshd",pid=1256518,fd=4),("sshd",pid=1256491,fd=4))
            SYN-SENT  0      1          10.0.0.169:45198 151.101.193.91:443   users:(("gnome-software",pid=1259638,fd=22))               
            ESTAB     0      0           127.0.0.1:38086      127.0.0.1:5902  users:(("sshd",pid=1258236,fd=7))                          
            TIME-WAIT 0      0          10.0.0.169:41180     10.0.4.244:636                                                              
            TIME-WAIT 0      0          10.0.0.169:53546     10.0.2.100:3128                                                             
            ESTAB     0      0           127.0.0.1:5901       127.0.0.1:49688 users:(("Xvnc",pid=952570,fd=23))                          
            SYN-SENT  0      1          10.0.0.169:40676 151.101.129.91:443   users:(("gnome-shell",pid=1259171,fd=34))                  
            ESTAB     0      0          10.0.0.169:22         10.0.1.53:41516 users:(("sshd",pid=1259753,fd=4),("sshd",pid=1259733,fd=4))
            ESTAB     0      0           127.0.0.1:49688      127.0.0.1:5901  users:(("sshd",pid=1256518,fd=7))                          
            ESTAB     0      0          10.0.0.169:22         10.0.1.53:39700 users:(("sshd",pid=1050325,fd=4),("sshd",pid=1050298,fd=4))
            TIME-WAIT 0      0          10.0.0.169:41178     10.0.4.244:636                                                              
            ESTAB     0      0          10.0.0.169:725       10.0.1.202:2049                                                             
            TIME-WAIT 0      0          10.0.0.169:53532     10.0.2.100:3128                                                             
            ESTAB     0      0          10.0.0.169:22         10.0.1.53:54592 users:(("sshd",pid=995013,fd=4),("sshd",pid=994974,fd=4))  
            TIME-WAIT 0      0          10.0.0.169:41196     10.0.4.244:636                                                              
            TIME-WAIT 0      0          10.0.0.169:41176     10.0.4.244:636                                                              
            SYN-SENT  0      1          10.0.0.169:49948 151.101.193.91:443   users:(("gnome-shell",pid=6978,fd=32))                     
            ESTAB     0      0           127.0.0.1:5902       127.0.0.1:38086 users:(("Xvnc",pid=1258996,fd=10))                         
            ESTAB     0      612        10.0.0.169:22        10.0.3.209:57353 users:(("sshd",pid=1258236,fd=4),("sshd",pid=1258006,fd=4))
            TIME-WAIT 0      0          10.0.0.169:53550     10.0.2.100:3128                                                             
            ESTAB     0      0          10.0.0.169:861       10.0.1.203:2049                                                             
            LISTEN    0      100             [::1]:25              [::]:*     users:(("master",pid=5337,fd=15))                          
            LISTEN    0      5               [::1]:5901            [::]:*     users:(("Xvnc",pid=952570,fd=7))                           
            LISTEN    0      5               [::1]:5902            [::]:*     users:(("Xvnc",pid=1258996,fd=7))                          
            LISTEN    0      128              [::]:111             [::]:*     users:(("rpcbind",pid=4410,fd=6),("systemd",pid=1,fd=44))  
            LISTEN    0      2048            [::1]:631             [::]:*     users:(("cupsd",pid=162159,fd=7))                          
        """)

    def test_two_vnc_connections(self):
        """Nominal test case for the Two VNC Connection test scenario

        This reaches a _bit_ more deeply into the code than a unit test
        perhaps should, but it is useful to keep track of some of the inner
        workings to make sure everything is handled properly.
        """

        command_output = TwoVncConnectionTestCase.command_output()
        invoke = ss.SSInvocation()
        with patch_subprocess_run("subprocess.run", command_output):
            invoke.run()

        expected_listening_ports = set([22, 25, 25, 111, 111, 631, 631, 5901,
                                        5901, 5902, 5902])
        actual_listening_ports=set(map(lambda s: s.port,
                                       invoke.listen_sockets))
        self.assertSetEqual(expected_listening_ports,
                            actual_listening_ports)

        expected_peer_pairs = set([
                (ip_address('10.0.1.53'), 39700),
                (ip_address('10.0.1.53'), 41516),
                (ip_address('10.0.1.53'), 54592),
                (ip_address('10.0.1.202'), 2049),
                (ip_address('10.0.1.203'), 2049),
                (ip_address('10.0.3.209'), 57343),
                (ip_address('10.0.3.209'), 57353),
                (ip_address('127.0.0.1'), 5901),
                (ip_address('127.0.0.1'), 5902),
                (ip_address('127.0.0.1'), 38086),
                (ip_address('127.0.0.1'), 49688)
        ])
        self.assertSetEqual(set(map(lambda x: (x[1], x[2]),
                                    invoke.established_sockets)),
                            expected_peer_pairs)

        expectedLoopbacks = [
            ss.LoopbackConnection(
                    client=ss.Socket(
                        addr=ip_address('127.0.0.1'),
                        port=38086,
                        processes=set([ss.SocketProcess(
                            comm="sshd",
                            pid=1258236
                        )])
                    ),
                    server=ss.Socket(
                        addr=ip_address('127.0.0.1'),
                        port=5902,
                        processes=set([ss.SocketProcess(
                            comm="Xvnc",
                            pid=1258996
                        )])
                    )
            ),
            ss.LoopbackConnection(
                    client=ss.Socket(
                        addr=ip_address('127.0.0.1'),
                        port=49688,
                        processes=set([ss.SocketProcess(
                            comm="sshd",
                            pid=1256518
                        )])
                    ),
                    server=ss.Socket(
                        addr=ip_address('127.0.0.1'),
                        port=5901,
                        processes=set([ss.SocketProcess(
                            comm="Xvnc",
                            pid=952570
                        )])
                    )
            )
        ]

        self.assertListEqual(expectedLoopbacks,
                             invoke.loopback_connections)
