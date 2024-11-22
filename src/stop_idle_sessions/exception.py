"""Common exception for indicating problems when parsing session info"""


class SessionParseError(Exception):
    """Common exception for indicating problems when parsing session info"""

    def __init__(self, message):
        self.message = message
