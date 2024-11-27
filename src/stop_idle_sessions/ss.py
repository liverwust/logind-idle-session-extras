"""Established network socket information using `ss`"""


from ipaddress import IPv4Address, IPv6Address, ip_address
import re
import subprocess
from typing import List, NamedTuple, Tuple, Union

from . import list_set, ps
from .exception import SessionParseError


class Socket(NamedTuple):
    """Represent a socket potentially associated with several processes

    Perhaps confusingly, Linux (and UNIX) allow multiple processes to share a
    single socket in the abstract socket namespace. This is very common in the
    case of parent/child forked processes, where a parent retains a file
    descriptor representing the socket and also endows the same to its child.
    That's why more than one ProcessSocket object can participate in both
    sides.
    """

    # An IPv4Address or IPv6Address associated with the local socket
    addr: Union[IPv4Address, IPv6Address]

    # TCP port number associated with the established TCP socket
    port: int

    # Zero or more Processes associated with the local socket
    processes: List[ps.Process]

    def __eq__(self, other):
        if not hasattr(other, 'addr'):
            return False

        if self.addr.is_loopback and other.addr.is_loopback:
            # Don't process the addresses if they are both loopback
            pass
        elif self.addr != other.addr:
            return False

        if not hasattr(other, 'port') or self.port != other.port:
            return False

        if not hasattr(other, 'processes'):
            return False

        if not list_set.compare_list_sets(self.processes, other.processes):
            return False

        return True


class LoopbackConnection(NamedTuple):
    """Represent a loopback TCP connection between two LocalSockets"""

    # One or more processes bound to the "client" side of the connection
    client: Socket

    # One or more processes bound to the "server" side of the connection
    server: Socket

    def __eq__(self, other):
        if not hasattr(other, 'client') or self.client != other.client:
            return False

        if not hasattr(other, 'server') or self.server != other.server:
            return False

        return True


class SSInvocation:
    """Collect context derived from an invocation of of the 'ss' command

    Users are not intended to instantiate this class directly. Please just see
    the find_loopback_connections function below, instead.
    """

    # A set of Sockets which are known to be listening.
    listen_sockets: List[Socket]

    # Associations of Sockets which are known to be part of an established
    # connection, along with the peer address and port numbers they are
    # connected to.
    established_sockets: List[Tuple[Socket,
                                    Union[IPv4Address,
                                          IPv6Address],
                              int]]

    # A collection of LocalConnections which have been extracted from the
    # previously-populated established_sockets.
    loopback_connections: List[LoopbackConnection]

    def __init__(self):
        self.listen_sockets = []
        self.established_sockets = []
        self.loopback_connections = []

    # There are a lot of local variables, but it's a complex problem
    # pylint: disable-next=too-many-locals
    def step_1_obtain_raw_ss_data(self):
        """Run 'ss' and populate the initial collections

        This is the first phase of a multi-phase operation. At the end of this
        phase, the listen_sockets will be populated and so will the
        established_sockets. The latter will contain ALL established
        connections for now.
        """

        try:
            cp = subprocess.run(["/usr/sbin/ss",
                                "--all",
                                "--no-header",
                                "--numeric",
                                "--oneline",
                                "--processes",
                                "--tcp"],
                                encoding='utf-8',
                                stdout=subprocess.PIPE,
                                check=True)
        except subprocess.CalledProcessError as err:
            raise SessionParseError('Could not read network connections from '
                                    'system `ss` command') from err

        # LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=5533,fd=3))
        socket_re = re.compile(r'^(?P<State>[-A-Z]+)\s+'
                            r'(?P<RecvQ>\d+)\s+'
                            r'(?P<SendQ>\d+)\s+'
                            r'\[?(?P<LocalAddress>[:.0-9]+)\]?:'
                            r'(?P<LocalPort>\d+)\s+'
                            r'\[?(?P<PeerAddress>[:.0-9]+)\]?:'
                            r'(?P<PeerPort>\d+|\*)\s*'
                            r'(users:\((?P<Process>.*)\))?\s*$')

        # ("rpcbind",pid=4935,fd=4),("systemd",pid=1,fd=327)
        paren_re = re.compile(r'[()]')
        comm_re = re.compile(r'^"(.*)"$')
        pid_re = re.compile(r'^pid=(\d+)$')
        # UNUSED
        #fd_re = re.compile(r'^fd=(\d+)$')

        for socket_line in cp.stdout.splitlines():
            socket_match = socket_re.match(socket_line)
            if socket_match is None:
                raise ValueError(f'invalid socket spec detected: '
                                 f'"{socket_line}"')

            processes: List[ps.Process] = []
            if socket_match.group('Process') is not None:
                process_clause = socket_match.group('Process')
                process_without_parens = paren_re.sub('', process_clause)
                process_parts = process_without_parens.split(',')

                if len(process_parts) % 3 != 0:
                    raise SessionParseError(f'invalid process spec detected: '
                                            f'"{process_clause}"')

                for base in range(0, len(process_parts) // 3):
                    individual_parts = process_parts[base*3:(base+1)*3]

                    comm_match = comm_re.match(individual_parts[0])
                    pid_match = pid_re.match(individual_parts[1])
                    if (comm_match is None or
                        pid_match is None):
                        raise SessionParseError(f'invalid process spec '
                                                f'detected: "{process_clause}"')

                    processes.append(ps.Process(
                        pid=int(pid_match.group(1)),
                        # This needs to be blank -- we can't get it from ss
                        cmdline="",
                        environ={}
                    ))

            if socket_match.group('State') == 'LISTEN':
                self.listen_sockets.append(Socket(
                    addr=ip_address(socket_match.group('LocalAddress')),
                    port=int(socket_match.group('LocalPort')),
                    processes=processes
                ))
            elif socket_match.group('State') == 'ESTAB':
                self.established_sockets.append((
                    Socket(
                        addr=ip_address(socket_match.group('LocalAddress')),
                        port=int(socket_match.group('LocalPort')),
                        processes=processes
                    ),
                    ip_address(socket_match.group('PeerAddress')),
                    int(socket_match.group('PeerPort'))
                ))

    def step_2_pair_loopback_peers(self):
        """Identify established connection pairs to loopback addresses

        This is the second phase of a multi-phase operation. At the end of
        this phase, the loopback_connections collection will have been
        populated with instances that represent established_sockets whose
        peer addresses belong to the loopback interface.

        Notably, the loopback_connections may contain loopback connections
        where the client/server directionality has been reversed (i.e., client
        is shown as server, and server as client). This will be fixed in the
        subsequent phase.
        """

        for (idx, socket_tuple) in enumerate(self.established_sockets):
            (socket, peer_addr, peer_port) = socket_tuple

            # Find the opposite side of the connection
            range_start = idx + 1
            range_end = len(self.established_sockets)
            candidates = self.established_sockets[range_start:range_end]
            for (candidate, candidate_addr, candidate_port) in candidates:
                if (socket.addr == candidate_addr and
                    socket.port == candidate_port and
                    candidate.addr == peer_addr and
                    candidate.port == peer_port):
                    self.loopback_connections.append(LoopbackConnection(
                        client=socket,
                        server=candidate
                    ))

    def step_3_identify_listener_services(self):
        """Reorient loopback connection pairs based on listening services

        Given that a LoopbackConnection involves two endpoints on the same
        machine, it should be easy to determine which one is actually the
        "server" in this context and which is the "client." The "server" is
        associated with a listening port.
        """

        for idx, loopback_connection in enumerate(self.loopback_connections):
            if loopback_connection.client in self.listen_sockets:
                self.loopback_connections[idx] = LoopbackConnection(
                        client=loopback_connection.server,
                        server=loopback_connection.client
                )

    def run(self):
        """Apply all three steps in sequence"""
        self.step_1_obtain_raw_ss_data()
        self.step_2_pair_loopback_peers()
        self.step_3_identify_listener_services()


def find_loopback_connections() -> List[LoopbackConnection]:
    """Obtain the full set of "loopback connections" on the local system

    A "loopback connection" is a pair of TCP sockets -- one client, and one
    server -- where both exist in the context of the local system and traverse
    the loopback adapter.
    """

    ss = SSInvocation()
    ss.run()
    return ss.loopback_connections
