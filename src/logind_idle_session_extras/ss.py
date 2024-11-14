"""Established network socket information using `ss`"""


from ipaddress import IPv4Address, IPv6Address, ip_address
import re
import subprocess
from typing import Collection, Mapping, NamedTuple, Tuple, Union


class ProcessSocket(NamedTuple):
    """Represent an established TCP socket belonging to a local process"""

    # An IPv4Address or IPv6Address associated with the local socket
    addr: Union[IPv4Address, IPv6Address]

    # TCP port number associated with the established TCP socket
    port: int

    # Short name of the process image (e.g., "sshd") bound to this socket
    comm: str

    # Process identifier (PID) of the process bound to this socket
    pid: int

    # File descriptor number within the process representing this socket
    fd: int


class LoopbackConnection:
    """Represent a loopback TCP connection between two LocalSockets

    Perhaps confusingly, Linux (and UNIX) allow multiple processes to share a
    single socket in the abstract socket namespace. This is very common in the
    case of parent/child forked processes, where a parent retains a file
    descriptor representing the socket and also endows the same to its child.
    That's why more than one ProcessSocket object can participate in both
    sides.

    Any LoopbackConnection object created by this ss.py Python module will
    guarantee that all of the client[*].port values are equal to one another,
    and that all of the server[*].port values are equal to one another.
    """

    # One or more processes bound to the "client" side of the connection
    client: Collection[ProcessSocket]

    # One or more processes bound to the "server" side of the connection
    server: Collection[ProcessSocket]

    def __eq__(self, other):
        if not isinstance(other, LoopbackConnection):
            return False

        my_client_set = frozenset(self.client)
        other_client_set = frozenset(other.client)
        my_server_set = frozenset(self.server)
        other_server_set = frozenset(other.server)

        # During the original computation, it is difficult to tell initially
        # whether a given TCP connection is oriented one way (local = client
        # and peer = server) or the other way (local = server and peer =
        # client). Allow these cases to be easily identified by considering a
        # LoopbackConnection to be equivalent regardless of this orientation.

        return ((my_client_set == other_client_set and
                 my_server_set == other_server_set) or
                (my_client_set == other_server_set and
                 my_server_set == other_client_set))


def _obtain_raw_ss_data() -> Tuple[Collection[ProcessSocket],
                                   Mapping[ProcessSocket,
                                           Tuple[Union[IPv4Address,
                                                       IPv6Address],
                                                 int]]]:
    """Use the 'ss' command to obtain data for identifying LoopbackConnections

    This is the first phase of a multi-phase operation. At the end of this
    function, a tuple is returned with two elements. The first is a set of
    ProcessSockets which are known to be listening.

    The second is a map of ProcessSockets which are known to be part of an
    established connection; to the peer addresses and port numbers they are
    connected to.
    """

    cp = subprocess.run(["/usr/sbin/ss",
                         "--all",
                         "--no-header",
                         "--numeric",
                         "--oneline",
                         "--processes",
                         "--tcp"],
                        encoding='utf-8',
                        stdout=subprocess.PIPE)

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
    fd_re = re.compile(r'^fd=(\d+)$')

    listen_sockets = []
    established_sockets = {}

    for socket_line in cp.stdout.splitlines():
        socket_match = socket_re.match(socket_line)
        if socket_match is None:
            raise ValueError('invalid socket spec detected in output of ss: "{}"',
                             socket_line)

        if socket_match.group('Process') is not None:
            process_clause = socket_match.group('Process')
            process_without_parens = paren_re.sub('', process_clause)
            process_parts = process_without_parens.split(',')

            if len(process_parts) % 3 != 0:
                raise ValueError('invalid structure for process clause: "{}"',
                                 process_clause)

            for base in range(0, len(process_parts) // 3):
                individual_parts = process_parts[base*3:(base+1)*3]

                comm_match = comm_re.match(individual_parts[0])
                pid_match = pid_re.match(individual_parts[1])
                fd_match = fd_re.match(individual_parts[2])
                if comm_match is None or pid_match is None or fd_match is None:
                    raise ValueError('invalid structure for process clause: "{}"',
                                    process_clause)

                individual_socket = ProcessSocket(
                    addr=ip_address(socket_match.group('LocalAddress')),
                    port=int(socket_match.group('LocalPort')),
                    comm=comm_match.group(1),
                    pid=int(pid_match.group(1)),
                    fd=int(fd_match.group(1))
                )

                if socket_match.group('State') == 'LISTEN':
                    listen_sockets.append(individual_socket)
                elif socket_match.group('State') == 'ESTAB':
                    established_sockets[individual_socket] = (
                            ip_address(socket_match.group('PeerAddress')),
                            int(socket_match.group('PeerPort'))
                    )

    return (listen_sockets, established_sockets)
