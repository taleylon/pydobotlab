"""Firmware-queue helpers.

The Dobot Magician has an on-board command queue. Most "set" commands accept
an ``isQueued`` flag in the control byte: when set, the firmware enqueues the
command and returns its position in the queue (a uint64 index) instead of
acting immediately. A separate set of control commands starts/stops/clears
the execution of that queue.

This module exposes that mechanism as a Python context manager:

    with dobot.batch():
        for x, y in path:
            dobot.ptp(PTPMode.MOVL_XYZ, x, y, 0, 0)

Inside the ``with`` block, queue execution is paused and commands are only
queued. On exit, the arm runs them and the block waits until they finish.
If the block raises, the queued commands are discarded instead.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .device import Dobot


class BatchState:
    """Per-Dobot state for nested batches.

    A counter rather than a boolean so that nested ``with dobot.batch():``
    blocks DTRT - only the outermost block actually pauses/resumes the queue.
    """

    __slots__ = ("depth", "lock")

    def __init__(self) -> None:
        self.depth = 0
        self.lock = threading.Lock()


@contextmanager
def batch_context(dobot: Dobot):
    """Implementation of ``Dobot.batch()`` - see :class:`pydobotlab.Dobot`.

    Paused → enqueue commands → resumed and waited for. The outer block also
    clears the queue on entry, so callers never inherit leftover state from a
    previous run.
    """
    state = dobot._batch_state  # noqa: SLF001 (intentional internal access)
    with state.lock:
        if state.depth == 0:
            dobot.stop_queue()
            dobot.clear_queue()
        state.depth += 1
    try:
        yield dobot
    except BaseException:
        with state.lock:
            state.depth -= 1
            is_outermost = state.depth == 0
        if is_outermost:
            dobot.clear_queue()
            dobot.start_queue()
        raise
    with state.lock:
        state.depth -= 1
        is_outermost = state.depth == 0
    if is_outermost:
        dobot.start_queue()
        dobot.wait_idle()
