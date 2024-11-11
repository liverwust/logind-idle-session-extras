# logind-idle-session-extras

Refresh systemd-logind idle timeouts based on supplemental user activity (e.g.,
VNC tunnel).

## Background

The Defense Information Systems Agency (DISA) Security Technical Implementation
Guide (STIG) for Red Hat Enterprise Linux (RHEL) 8 includes the following
technical control:

[V-257258: Terminating an idle session within a short time period reduces the
window of opportunity for unauthorized personnel to take control of
a management session enabled on the console or console port that has been left
unattended.](https://www.stigviewer.com/stig/red_hat_enterprise_linux_8/2023-09-11/finding/V-257258)

The implementation which is prescribed for this technical control is as follows:

```bash
# Verify that RHEL 8 logs out sessions that are idle for 15 minutes with the following command:
$ sudo grep -i ^StopIdleSessionSec /etc/systemd/logind.conf
StopIdleSessionSec=900
# If "StopIdleSessionSec" is not configured to "900" seconds, this is a finding. 
```

For a non-graphical session, such as one launched from the local console or
from SSH, the [StopIdleSessionSec
setting](https://www.freedesktop.org/software/systemd/man/latest/logind.conf.html#StopIdleSessionSec=)
(`man 5 logind.conf`) uses the `atime` (access time) of the tty or pty device
to determine idleness. If the `atime` is older than the specified threshold,
then the session is terminated.

Although this behavior is desirable from a security standpoint, it can have
adverse effects on user experience. This repository is intended to mitigate
some of these adverse effects by using supplemental sources of information to
arrive at a more "forgiving" assessment of user activity associated with
a particular session.

## Runtime Behavior

The `logind-idle-session-extras` package provides a Python script which can be
run as a SystemD service. Its purpose is to monitor sessions (`man
8 systemd-logind.service`) for a few distinct activity conditions. If any of
those conditions are detected, then it will "refresh" the associated user
session by updating the `atime` of the associated tty or pty device.

### Condition 1: `mtime` is newer than `atime`

In the context of a non-graphical session, it is obvious that a user's
keystrokes should be counted as "activity" on the user's part. To borrow
wording from the STIG control: it is nearly certain that a console session
which is registering keystrokes has not been *left unattended*.

A less obvious scenario involves a program which is continuously generating new
output, such as the output from a compiler or a scripted shell loop. A user
might have started such a process and then walked away. There is a tradeoff
between security (= uncertainty about whether the console has been *left
unattended*) and functionality (= unwillingness to terminate a process that the
user has chosen to launch, but which doesn't require much input right now).

Interestingly, the following patterns can be observed empirically — e.g., by
running `man 1 inotifywatch` against a tty or pty:

| Event          | Updates `mtime`? | Updates `atime`? |
|----------------|------------------|------------------|
| Keyboard input | Yes              | Yes              |
| Program output | Yes              | **No**           |

If `logind-idle-session-extras` is configured to look for Condition 1, then it
will find tty and pty devices whose `mtime` is newer than its `atime`. It will
then update the `atime` to match the `mtime`. This will allow the behavior of
programs which are actively writing to the console to extend the idle timeout.

Note that programs which are displaying static output will NOT touch the
`mtime` and will therefore not be successful at extending the idle timeout. For
instance, a console session which is displaying a manpage for longer than the
threshold will be terminated at the timeout interval.

### Condition 2: The sshd child process has established tunnels

One particularly important type of non-graphical session is associated with
a remote connection via SSH. In this case, the "session leader" process (i.e.,
the process whose PID is equal to its Process Group ID) will be a child forked
from the `sshd` daemon process.

[OpenSSH provides various forwarding
features](https://www.openssh.com/features.html), which can be used to instruct
the server to "tunnel" traffic to/from remote locations on behalf of the
client. This means that a console session's continued existence might affect
more than just the interactive terminal session itself.

If `logind-idle-session-extras` is configured to look for Condition 2, but
without any further refinement (see condition 2A for an example of this), then
it will find `sshd` session leader processes which are bound to connected or
listening network sockets. As long as these sockets exist,
`logind-idle-session-extras` will touch the `atime` for the associated pty to
ensure that the session stays alive.

### Condition 2A: The establish tunnels include a connection to an active VNC session

This is a refinement of Condition 2. It may not be desirable to allow *any*
forwarding tunnel to hold open an SSH session. Instead,
`logind-idle-session-extras` can check whether any of the connected sockets
terminate at a local VNC service. If so, it can further trace the state of that
VNC service to its own session identifier, and use that session's activity
status to either update or skip updating the `atime` on the SSH pty.

In doing so, the idle-or-not-idle status of the VNC session is propagated to
the SSH session. For instance, when a user walks away from their VNC session,
it will eventually be subject to its own idle timeout (which is usually
accompanied by a screen-lock mechanism). Only _after_ that happens will the SSH
session also be subject to an idle timeout.
