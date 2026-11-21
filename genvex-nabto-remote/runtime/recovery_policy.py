"""Offline candidate recovery policy for intermittent legacy Nabto RPC45 errors.

Only used by the manually requested --recover-once single-shot test.
Not wired to the HAOS App, ordinary live reads or Home Assistant coordinator.
A fresh SDKSnapshotAdapter.poll_once() starts and cleans up a separate SDK
process for each attempt. No persistent session and no hidden background loop.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sdk_snapshot_adapter import SDKSnapshotError

# Observed in the isolated field trial. This is a diagnostic event, not
# an independently verified mapping of nabtoRpcInvoke's return status.
_TRANSIENT_EVENT = 1000015
_RETRY_DELAY_SECONDS = 60.0


def eligible_for_one_retry(error: BaseException) -> bool:
    """Fail closed on absent/ambiguous diagnostics, timeout or other failures."""
    return (
        isinstance(error, SDKSnapshotError)
        and error.code == "SDK_RPC45_FAILED"
        and error.rpc_status == 26
        and error.rpc_events == (_TRANSIENT_EVENT,)
    )


async def read_with_one_recovery(
    poll_once: Callable[[], Awaitable[dict[str, Any]]],
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    """Exactly one first attempt; at most one *new* attempt after 60 seconds.

    This callable is used only by an explicit manual experiment; offline
    regression tests cover the policy without any SDK or network.
    Non-eligible failures pass through unchanged. Cancellation must interrupt
    any attempt or the delay. No credentials or error text are logged.
    """
    try:
        return await poll_once()
    except asyncio.CancelledError:
        raise
    except SDKSnapshotError as error:
        if not eligible_for_one_retry(error):
            raise
    await sleep(_RETRY_DELAY_SECONDS)
    return await poll_once()
