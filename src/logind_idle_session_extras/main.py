"""Main logic for the logind-idle-session-extras loop"""


import pprint
from typing import Collection

from . import logind, ps, rules, ss


def iterate():
    """Run a single iteration of the logind-idle-session-extras logic"""

    with open('rules.json', 'rb') as in_j:
        all_rules = rules.parse_rules_from_json(in_j)

    logind_manager = logind.Manager()
    logind_sessions = logind_manager.get_all_sessions()
    loopback_connections = ss.find_loopback_connections()

    sessions: Collection[rules.Session] = []
    for logind_session in logind_sessions:
        session_processes: Collection[SessionProcess] = []
        for ps_obj in ps.processes_in_scope_path(logind_session.scope_path):
            tunnels: Collection[rules.Process] = []
            for loopback_connection in loopback_connections:
                for client_process in loopback_connection.client.processes:
                    for server_process in loopback_connection.server.processes:
                        if client_process.pid == ps_obj.pid:
                            server_process_obj = rules.Process(
                                    pid=server_process.pid,
                                    comm=server_process.comm,
                                    cmdline=""
                            )
                            if not server_process_obj in tunnels:
                                tunnels.append(server_process_obj)

            session_processes.append(rules.SessionProcess(
                    process=rules.Process(
                        pid=ps_obj.pid,
                        comm=ps_obj.name(),
                        cmdline=' '.join(ps_obj.cmdline())
                    ),
                    leader=(ps_obj.pid == logind_session.leader),
                    tunnels=tunnels
            ))

        sessions.append(rules.Session(
                session_id=logind_session.session_id,
                uid=logind_session.uid,
                leader_pid=logind_session.leader,
                tty=logind_session.tty,
                processes=session_processes
        ))

    pprint.pprint(sessions)
    pprint.pprint(all_rules)
