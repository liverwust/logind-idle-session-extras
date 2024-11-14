"""Established network socket information using `ss`"""


from ipaddress import IPv4Address, IPv6Address, ip_address
import re
import subprocess
from typing import Collection, Mapping, NamedTuple, Optional, Tuple, Union


class SocketProcess(NamedTuple):
    """Represent a single local process associated with a Socket"""

    # Short name of the process image (e.g., "sshd") bound to this socket
    comm: str

    # Process identifier (PID) of the process bound to this socket
    pid: int

    # File descriptor number within the process representing this socket
    fd: int

    def __eq__(self, other):
        if not isinstance(other, SocketProcess):
            return False
        return (self.comm == other.comm and
                self.pid == other.pid and
                self.fd == other.fd)


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

    # Zero or more SocketProcesses associated with the local socket
    processes: Collection[SocketProcess]

    def __eq__(self, other):
        if not isinstance(other, Socket):
            return False
        elif self.addr != other.addr:
            return False
        elif self.port != other.port:
            return False
        elif len(self.processes) != len(other.processes):
            return False
        else:
            other_processes = list(other.processes)
            for my_process in self.processes:
                try:
                    other_idx = other_processes.find(my_process)
                    del other_processes[other_idx]
                except ValueError:
                    return False
            return True

class LoopbackConnection(NamedTuple):
    """Represent a loopback TCP connection between two LocalSockets"""

    # One or more processes bound to the "client" side of the connection
    client: Socket

    # One or more processes bound to the "server" side of the connection
    server: Socket


class _SSInvocation:
    """Collect context derived from an invocation of of the 'ss' command

    Users are not intended to instantiate this class directly. Please just see
    the find_loopback_connections function below, instead.
    """

    # A set of Sockets which are known to be listening.
    _listen_sockets: Collection[Socket]

    # Associations of Sockets which are known to be part of an established
    # connection, along with the peer address and port numbers they are
    # connected to.
    _established_sockets: Collection[Tuple[Socket,
                                           Union[IPv4Address,
                                                 IPv6Address],
                                           int]]

    # A collection of LocalConnections which have been extracted from the
    # previously-populated _established_sockets.
    _loopback_connections: Collection[LoopbackConnection]

    def __init__(self):
        self._listen_sockets = []
        self._established_sockets = []
        self._loopback_connections = []

    def _step_1_obtain_raw_ss_data(self):
        """Run 'ss' and populate the initial collections

        This is the first phase of a multi-phase operation. At the end of this
        phase, the _listen_sockets will be populated and so will the
        _established_sockets. The latter will contain ALL established
        connections for now.
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

        for socket_line in cp.stdout.splitlines():
            socket_match = socket_re.match(socket_line)
            if socket_match is None:
                raise ValueError('invalid socket spec detected: "{}"',
                                socket_line)

            if socket_match.group('Process') is not None:
                individual_socket = Socket(
                    addr=ip_address(socket_match.group('LocalAddress')),
                    port=int(socket_match.group('LocalPort')),
                    processes=[]
                )

                process_clause = socket_match.group('Process')
                process_without_parens = paren_re.sub('', process_clause)
                process_parts = process_without_parens.split(',')

                if len(process_parts) % 3 != 0:
                    raise ValueError('invalid process spec detected: "{}"',
                                    process_clause)

                for base in range(0, len(process_parts) // 3):
                    individual_parts = process_parts[base*3:(base+1)*3]

                    comm_match = comm_re.match(individual_parts[0])
                    pid_match = pid_re.match(individual_parts[1])
                    fd_match = fd_re.match(individual_parts[2])
                    if (comm_match is None or
                        pid_match is None or
                        fd_match is None):
                        raise ValueError('invalid process spec detected: "{}"',
                                        process_clause)

                    individual_socket.processes.append(SocketProcess(
                        comm=comm_match.group(1),
                        pid=int(pid_match.group(1)),
                        fd=int(fd_match.group(1))
                    ))

                if socket_match.group('State') == 'LISTEN':
                    self._listen_sockets.append(individual_socket)
                elif socket_match.group('State') == 'ESTAB':
                    self._established_sockets.append((
                        individual_socket,
                        ip_address(socket_match.group('PeerAddress')),
                        int(socket_match.group('PeerPort'))
                    ))

    def _step_2_pair_loopback_peers(self):
        """Identify established connection pairs to loopback addresses

        This is the second phase of a multi-phase operation. At the end of
        this phase, the _loopback_connections collection will have been
        populated with instances that represent _established_sockets whose
        peer addresses belong to the loopback interface.

        Notably, the _loopback_connections may contain loopback connections
        where the client/server directionality has been reversed (i.e., client
        is shown as server, and server as client). This will be fixed in the
        subsequent phase.
        """

        for (idx, socket_tuple) in enumerate(self._established_sockets):
            (socket, peer_addr, peer_port) = socket_tuple

            # Find the opposite side of the connection
            range_start = idx + 1
            range_end = len(self._established_sockets)
            candidates = self._established_sockets[range_start:range_end]
            for (candidate, candidate_addr, candidate_port) in candidates:
                if (socket.addr == candidate_addr and
                    socket.port == candidate_port and
                    candidate.addr == peer_addr and
                    candidate.port == peer_port):
                    self._loopback_connections.append(LoopbackConnection(
                        client=socket,
                        server=candidate
                    ))
