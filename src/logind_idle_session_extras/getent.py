"""Interact with getent passwd and the nsswitch backend"""


import subprocess
from typing import Optional


def uid_to_username(uid: int) -> Optional[str]:
    """Resolve a numeric user ID to a symbolic username

    Rather than using the built-in pwd module, this calls out to getent
    passwd. This is intended to support nsswitch, sssd, and things like LDAP
    or Active Directory backends (which introduce users that don't exist in
    passwd/shadow).
    """

    cp = subprocess.run(['/usr/bin/getent', 'passwd', str(uid)],
                        encoding='utf-8',
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        check=False)

    if cp.returncode == 0:
        return cp.stdout.split(":")[0]
    if cp.returncode == 2:
        # From man 1 getent, this means: "One or more supplied key could not
        # be found in the database."
        return None
    raise RuntimeError(f"Unknown rc {cp.returncode} from getent "
                       f"with stderr: {cp.stderr}")
