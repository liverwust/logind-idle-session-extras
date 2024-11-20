"""Main logic unit tests, operating on the abstract Session/Process tree"""


from typing import List
from unittest import TestCase
from unittest.mock import Mock, patch

from logind_idle_session_extras import main


MOCK_SCOPE_NAMESPACE = '/notreal.slice/user-{0}.slice/{1}'


class LoadSessionsTestCase(TestCase):
    """Testing logic for the loading of the abstract session tree"""

    # Override during each test method to configure the mocked return list of
    # Sessions for this particular run. These Mocks should resemble
    # logind.Session objects.
    _all_sessions: List[Mock]

    def setUp(self):
        get_all_sessions = Mock(side_effect=lambda: self._all_sessions)
        get_all_sessions_patcher = patch('logind.get_all_sessions',
                                         new=get_all_sessions)
        get_all_sessions_patcher.start()
        self.addCleanup(get_all_sessions_patcher.stop)

    # pylint: disable-next=too-many-positional-arguments, too-many-arguments
    def _create_mock_session(self,
                             session_id: str,
                             uid: int,
                             tty: str,
                             leader: int,
                             scope: str):
        session = Mock()
        session.session_id = Mock(return_value=session_id)
        session.uid = Mock(return_value=uid)
        session.tty = Mock(return_value=tty)
        session.leader = Mock(return_value=leader)
        session.scope = Mock(return_value=scope)
        scope_path = MOCK_SCOPE_NAMESPACE.format(uid, scope)
        session.scope_path = Mock(return_value=scope_path)
        return session

    def test_load_sessions_unit(self):
        """Nominal test case for a minimally complex session structure"""

        self._all_sessions = []
        self._all_sessions.append(self._create_mock_session(
                "1267",
                1002,
                "pts/2",
                952165,
                "session-1267.scope"
        ))
        self._all_sessions.append(self._create_mock_session(
                "1301",
                0,
                "pts/1",
                994974,
                "session-1301.scope",
        ))
        self._all_sessions.append(self._create_mock_session(
                "1337",
                1002,
                "pts/0",
                1050298,
                "session-1337.scope",
        ))
        self._all_sessions.append(self._create_mock_session(
                "c1",
                42,
                "tty1",
                5655,
                "session-c1.scope",
        ))
