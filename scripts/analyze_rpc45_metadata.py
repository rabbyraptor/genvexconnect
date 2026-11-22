#!/usr/bin/env python3
"""Parse sanitized RPC45 cycle logs into a bounded, metadata-only summary.

Offline utility, never opens an SDK session or requests credentials.
Unknown input is ignored and never echoed, including secrets or raw SDK JSON.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sys

MAX_LINES = 10000
MAX_LINE_BYTES = 2048
_CYCLE = re.compile(
    r"(?:^|\\s)RPC45 "
    r"(?P<timestamp>\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d(?:\\.\\d+)?(?:Z|[+-]\\d\\d:\\d\\d)) "
    r"(?P<state>OK|FEJL) "
    r"(?P<duration>\\d+(?:\\.\\d{1,3})?)s "
    r"PID_BEFORE=(?P<before>None|\\d{1,9}) PID_AFTER=(?P<after>None|\\d{1,9})$"
)


def analyze_lines(lines) -> dict:
    """Return statistics only; never forward a raw log line."""
    cycles = []
    ignored = 0
    total = 0
    for line in lines:
        total += 1
        if total > MAX_LINES:
            raise ValueError("Too many diagnostic lines")
        if not isinstance(line, str) or len(line.encode("utf-8")) > MAX_LINE_BYTES:
            ignored += 1
            continue
        match = _CYCLE.search(line.strip())
        if not match:
            ignored += 1
            continue
        try:
            stamp = datetime.fromisoformat(
                match.group("timestamp").replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            duration = float(match.group("duration"))
            before, after = match.group("before", "after")
            if duration > 120 or (cycles and stamp <= cycles[-1][0]):
                ignored += 1
                continue
            cycles.append((stamp, match.group("state") == "OK", before, after))
        except ValueError:
            ignored += 1
    failures = [i for i, record in enumerate(cycles) if not record[1]]
    intervals = [
        round((cycles[j][0] - cycles[i][0]).total_seconds(), 2)
        for i, j in zip(failures, failures[1:])
    ]
    recovered_next = sum(
        1 for i in failures if i + 1 < len(cycles) and cycles[i + 1][1]
    )
    worker_reused_on_recovery = sum(
        1 for i in failures
        if i + 1 < len(cycles) and cycles[i + 1][1]
        and cycles[i][3] != "None"
        and cycles[i][3] == cycles[i + 1][2] == cycles[i + 1][3]
    )
    return {
        "cycles": len(cycles),
        "successes": len(cycles) - len(failures),
        "failures": len(failures),
        "recovered_next_cycle": recovered_next,
        "worker_reused_on_recovery": worker_reused_on_recovery,
        "failure_intervals_seconds": intervals,
        "ignored_lines": ignored,
    }


def main() -> int:
    try:
        result = analyze_lines(sys.stdin)
    except (ValueError, UnicodeError):
        print('{"error":"invalid_diagnostic_input"}')
        return 2
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
