# DEV8 — opt-in sensor projection gate (no live activation)

This branch extends the existing offline seven-address RPC45/v2 snapshot
prototype. The combined read addresses are `20,21,22,23,26,18,19`;
the two additional addresses are provisional fan-duty readings pending
comparison with the official Genvex Connect UI. No HAOS runtime changes or
live Nabto requests occur in this PR.

The pure `ha_v2_projection.project_v2_sensors` function now supports
`include_fan_duty=False` to produce the legacy five measurement entities
while validating the full incoming v2 contract. When explicitly requested,
`include_fan_duty=True` preserves the existing seven-row offline projection.
The gate accepts only real booleans (never `0`, `1`, or strings).

Both projections keep stable keys and the v1 unique-ID rule. Optional fan
values are either a complete validated pair or unavailable; unavailable
means `None`, not a fabricated zero. Existing five-value v1 API and HA
Core entity registration remain unchanged.

## Source-only gate

```sh
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
```

## Live gate, pending approval

1. Compare address 18 and 19 raw values with official UI under multiple fan
   speeds, verifying interpretation and order.
2. Validate seven-address RPC45 on HAOS/QEMU with the same SDK profile,
   checking snapshot freshness and retry behavior.
3. Review whether the HA integration should expose an opt-in seventh sensor
   set, with no migration of the five legacy unique IDs.
4. Deploy only after the above results are documented and approved.
