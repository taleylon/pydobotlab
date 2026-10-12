"""Explain *why* a serial port could not be opened due to permissions.

On Linux a serial device such as ``/dev/ttyACM0`` is owned by a group
(``dialout`` on Debian/Ubuntu) and a user can only open it after being
added to that group, and starting a new login session.
Opening without that fails with "permission denied".

:func:`diagnose_port_permission` checks the device node itself instead of
guessing from an error string, so a permission message is only produced when
access is genuinely missing.
"""

from __future__ import annotations

import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PortPermissionProblem:
    """A confirmed lack of access to a serial device, with the fix."""

    reason: str  # "not_in_group", "needs_new_login", or "no_group_access"
    message: str


def describe_permission_problem(
    port: str,
    *,
    group_name: str,
    device_mode: int,
    user_name: str,
    group_members: Collection[str],
    user_is_in_group_now: bool,
) -> PortPermissionProblem:
    """Say what blocks ``user_name`` from a device that is already known to be inaccessible.

    ``user_is_in_group_now`` is whether the *running session* has the
    device's group; ``group_members`` is who the system databases list in it.
    """
    group_can_read_write = (device_mode & 0o060) == 0o060
    if not group_can_read_write:
        return PortPermissionProblem(
            "no_group_access",
            f"Permission denied for {port}: the device is not read/write for "
            f"group '{group_name}' (mode {device_mode & 0o777:03o}), so adding "
            f"yourself to that group will not help. Check: ls -l {port}",
        )
    if user_is_in_group_now:
        return PortPermissionProblem(
            "no_group_access",
            f"Permission denied for {port} even though you are in group "
            f"'{group_name}'. Check: ls -l {port} (and any SELinux/AppArmor policy).",
        )
    if user_name in group_members:
        return PortPermissionProblem(
            "needs_new_login",
            f"Permission denied for {port}: you were added to group "
            f"'{group_name}' but this session started before that. "
            f"Log out and back in (or restart) for it to take effect.",
        )
    return PortPermissionProblem(
        "not_in_group",
        f"Permission denied for {port}: your user is not in the "
        f"'{group_name}' group. Run: sudo usermod -aG {group_name} $USER "
        f"then log out and back in (or restart).",
    )


def diagnose_port_permission(port: str) -> PortPermissionProblem | None:
    """Return the confirmed permission problem for ``port``, or ``None``.

    ``None`` means this user can read and write the device (or the platform
    has no device-node permissions, like Windows), so a failed open is not a
    permission problem.
    """
    device_path = Path(port)
    if os.name != "posix" or not device_path.exists():
        return None
    if os.access(port, os.R_OK | os.W_OK):
        return None

    import grp
    import pwd

    device_status = device_path.stat()
    group_id = device_status.st_gid
    try:
        group = grp.getgrgid(group_id)
        group_name, group_members = group.gr_name, group.gr_mem
    except KeyError:
        group_name, group_members = str(group_id), []
    return describe_permission_problem(
        port,
        group_name=group_name,
        device_mode=device_status.st_mode,
        user_name=pwd.getpwuid(os.getuid()).pw_name,
        group_members=group_members,
        user_is_in_group_now=group_id == os.getgid() or group_id in os.getgroups(),
    )
