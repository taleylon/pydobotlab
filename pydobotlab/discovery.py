"""Find Dobot Magicians on the local machine.

This module deliberately lives *outside* the :class:`Dobot` class — discovery
is independent of any one device, and a :class:`Dobot` instance should never
need to know how it was found.

Two strategies are exposed, plus a :class:`Discovery` namespace that wraps
both for callers who prefer the class-method style:

* :func:`list_ports` enumerates serial ports the OS sees and flags ones whose
  USB VID/PID matches a known Dobot adapter. Fast, side-effect free, but a
  USB-serial dongle for *something else* could also match.
* :func:`discover` opens each candidate, sends ``GetDeviceSN`` and waits for
  a response. Slower but authoritative — anything in the result really is a
  Dobot, and the serial number lets you pin a particular arm to a particular
  variable across sessions.

USB IDs
~~~~~~~
``KNOWN_DOBOT_USB_IDS`` lists VID/PID pairs verified to ship with Dobot
Magicians. It is a regular ``set`` and you can extend it at runtime if your
hardware revision uses a different adapter::

    from pydobotlab.discovery import KNOWN_DOBOT_USB_IDS
    KNOWN_DOBOT_USB_IDS.add((0x10C4, 0xEA60))
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .commands import CommandID
from .errors import DobotConnectionError, DobotPortInUseError
from .transport import SerialTransport, is_port_claimed

# Verified VID/PID pairs that have been observed shipping with the Dobot
# Magician. Currently only the WCH CH340 (the chip on every Magician seen in
# the wild) is in this list. If you find your kit uses a different adapter,
# add its (vid, pid) to this set at import time — :func:`list_ports` will then
# flag those ports as ``is_known_dobot_adapter=True``.
KNOWN_DOBOT_USB_IDS: set[tuple[int, int]] = {
    (0x1A86, 0x7523),  # WCH CH340 — the only adapter attested for Magicians
}


@dataclass(frozen=True, slots=True)
class PortInfo:
    """A serial port that *might* be a Dobot, with whatever metadata the OS exposes."""

    port: str
    description: str = ""
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None  # USB descriptor SN, not the Dobot SN
    is_known_dobot_adapter: bool = False
    is_claimed: bool = False


@dataclass(frozen=True, slots=True)
class DiscoveredDobot:
    """A port that responded to a Dobot probe."""

    port: str
    serial_number: str
    description: str = ""


# ---------------------------------------------------------------------------
# Module-level functions (the canonical API)
# ---------------------------------------------------------------------------


def list_ports(*, only_known_adapters: bool = False) -> list[PortInfo]:
    """Enumerate serial ports that could plausibly be Dobots.

    Parameters
    ----------
    only_known_adapters:
        If ``True``, drop ports whose USB VID/PID is not in
        :data:`KNOWN_DOBOT_USB_IDS`. Defaults to ``False`` so an arm behind a
        not-yet-seen adapter still shows up — the trade-off is that other USB
        serial devices (Arduinos, RS-485 dongles, …) appear too.
    """
    try:
        from serial.tools import list_ports as serial_ports
    except ImportError as error:  # pragma: no cover - pyserial is a hard dep
        raise DobotConnectionError(
            "pyserial is required for port discovery; "
            "install pydobotlab with `pip install -e .` or `pip install pyserial`"
        ) from error

    ports: list[PortInfo] = []
    for port_info in serial_ports.comports():
        is_known = (port_info.vid, port_info.pid) in KNOWN_DOBOT_USB_IDS
        if only_known_adapters and not is_known:
            continue
        ports.append(
            PortInfo(
                port=port_info.device,
                description=port_info.description or "",
                vid=port_info.vid,
                pid=port_info.pid,
                serial_number=port_info.serial_number,
                is_known_dobot_adapter=is_known,
                is_claimed=is_port_claimed(port_info.device),
            )
        )
    ports.sort(key=lambda port_info: (not port_info.is_known_dobot_adapter, port_info.port))
    return ports


def is_dobot(port: str, *, timeout: float = 0.4) -> bool:
    """Quickly probe ``port`` to see whether a Dobot answers.

    Sends ``GetDeviceSN`` (cmd ID 0) and returns ``True`` if a well-formed
    response comes back inside ``timeout`` seconds.
    """
    if is_port_claimed(port):
        # We hold it open already — by definition it answered our probe before.
        return True
    try:
        transport = SerialTransport(port, timeout=timeout)
        transport.open()
    except DobotConnectionError:
        return False
    try:
        try:
            transport.send_frame(CommandID.GET_DEVICE_SN, 0)
            return True
        except Exception:
            return False
    finally:
        transport.close()


@dataclass(frozen=True, slots=True)
class ProbeFailure:
    """A serial port that the probe tried to open or query but couldn't.

    Surfaced via :func:`discover_with_diagnostics` so callers can tell the
    user *why* a port was rejected — "permission denied", "didn't answer",
    "busy" — rather than silently dropping it. This is what the panel uses
    to explain ttyACM-on-Linux pitfalls (dialout group, brltty grabbing the
    device) instead of just saying "no Dobots found".
    """

    port: str
    description: str
    reason: str  # short label: "permission", "busy", "no_reply", "other"
    detail: str  # full error message


def discover(
    *,
    only_known_adapters: bool = False,
    timeout: float = 0.4,
    skip: Iterable[str] = (),
) -> list[DiscoveredDobot]:
    """Probe every candidate port; return ones that answer like a Dobot.

    Ports already claimed by a :class:`Dobot` instance in this process are
    skipped — :func:`is_port_in_use` will tell you about those.

    For diagnostics about ports that *were* probed but didn't answer (e.g. a
    /dev/ttyACM0 you don't have permission for), use
    :func:`discover_with_diagnostics`.
    """
    devices, _ = discover_with_diagnostics(
        only_known_adapters=only_known_adapters,
        timeout=timeout,
        skip=skip,
    )
    return devices


def discover_with_diagnostics(
    *,
    only_known_adapters: bool = False,
    timeout: float = 0.4,
    skip: Iterable[str] = (),
) -> tuple[list[DiscoveredDobot], list[ProbeFailure]]:
    """Same as :func:`discover`, but also returns the list of ports that
    *were* tried but didn't qualify, with a reason for each.

    Returns ``(hits, failures)``.

    Why this exists: on Linux the Magician sometimes enumerates as
    ``/dev/ttyACM0`` (CDC ACM driver) rather than ``/dev/ttyUSB0`` (CH340).
    If the user isn't in the ``dialout`` group, or if ``brltty`` has grabbed
    the device, opening it raises ``PermissionError`` / "device or resource
    busy". The plain :func:`discover` would just drop the port and the user
    sees "no Dobots found" with no hint why. With diagnostics, the panel can
    say "we tried /dev/ttyACM0 but got permission denied — add yourself to
    the dialout group" instead.
    """
    skip_set = set(skip)
    found: list[DiscoveredDobot] = []
    failed: list[ProbeFailure] = []

    for info in list_ports(only_known_adapters=only_known_adapters):
        if info.port in skip_set:
            continue
        if info.is_claimed:
            # Already held by a Magician in this process — not a failure.
            continue
        try:
            transport = SerialTransport(info.port, timeout=timeout)
            transport.open()
        except DobotPortInUseError as error:
            failed.append(
                ProbeFailure(
                    port=info.port,
                    description=info.description,
                    reason="busy",
                    detail=str(error),
                )
            )
            continue
        except DobotConnectionError as error:
            msg = str(error).lower()
            if "permission denied" in msg:
                reason = "permission"
            elif "device or resource busy" in msg or "in use" in msg:
                reason = "busy"
            else:
                reason = "other"
            failed.append(
                ProbeFailure(
                    port=info.port,
                    description=info.description,
                    reason=reason,
                    detail=str(error),
                )
            )
            continue
        # Port opened; now probe.
        try:
            try:
                frame = transport.send_frame(CommandID.GET_DEVICE_SN, 0)
                serial_number = frame.params.rstrip(b"\x00").decode("ascii", errors="replace")
                found.append(
                    DiscoveredDobot(
                        port=info.port,
                        serial_number=serial_number,
                        description=info.description,
                    )
                )
            except Exception as error:
                failed.append(
                    ProbeFailure(
                        port=info.port,
                        description=info.description,
                        reason="no_reply",
                        detail=str(error),
                    )
                )
        finally:
            transport.close()
    return found, failed


def find_free_port(*, only_known_adapters: bool = False) -> str | None:
    """Return the first available Dobot port, or ``None`` if there is none.

    "Available" means: enumerated by the OS, not currently held by any other
    :class:`Dobot` instance in this process, and answering to ``GetDeviceSN``.
    """
    devices = discover(only_known_adapters=only_known_adapters)
    return devices[0].port if devices else None


def is_port_in_use(port: str) -> bool:
    """``True`` iff ``port`` is currently held by a :class:`Dobot` in this process.

    A re-export of :func:`pydobotlab.transport.is_port_claimed` under a name that
    matches the rest of the discovery API.
    """
    return is_port_claimed(port)


# ---------------------------------------------------------------------------
# Class namespace (cosmetic alternative to the module-level functions)
# ---------------------------------------------------------------------------


class Discovery:
    """Class-style namespace that wraps the module-level discovery functions.

    Some users prefer ``Discovery.list_ports()`` over
    ``pydobotlab.discovery.list_ports()``. The two are exactly equivalent.
    """

    list_ports = staticmethod(list_ports)
    is_dobot = staticmethod(is_dobot)
    discover = staticmethod(discover)
    discover_with_diagnostics = staticmethod(discover_with_diagnostics)
    find_free_port = staticmethod(find_free_port)
    is_port_in_use = staticmethod(is_port_in_use)
