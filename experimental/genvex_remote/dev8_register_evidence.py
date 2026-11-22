"""DEV8.2 evidence-aware Optima 270 RPC45 inventory (offline, no SDK).

Source mapping: public Optima 270 datapoint model, represented by the
existing five-value capability catalog and twelve source-based candidates.

Live evidence: five baseline values repeatedly observed on HAOS; a single
12/12 remote batch on Steam Deck (2026-11-20); an additional seven-address
batch observed on both Steam Deck and HAOS/QEMU (2026-11-20).

A successfully read register is NOT proof of sensor semantics or hardware.
This inventory never permits production reads or entity registration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from capability_catalog import OPTIMA_270
from optima270_source_only import list_source_only_candidates


class EvidenceError(ValueError):
    """A source-backed mapping or raw RPC response violates the review gate."""


ReadEvidence = Literal[
    "haos_five_active",
    "haos_seven_once",
    "steamdeck_twelve_once",
]
SemanticEvidence = Literal[
    "baseline_validated",
    "app_correlated_not_simultaneous",
    "source_only_unverified",
]


@dataclass(frozen=True)
class RegisterEvidence:
    """One source-known address, independent transport and meaning evidence."""

    key: str
    object_id: int
    address: int
    read_evidence: ReadEvidence
    semantic_evidence: SemanticEvidence
    sample_raw: int | None

    @property
    def ready_for_ha(self) -> bool:
        """Only the five existing readings are approved without further review."""
        return (
            self.read_evidence == "haos_five_active"
            and self.semantic_evidence == "baseline_validated"
        )

    @property
    def candidate_for_fan_projection(self) -> bool:
        return (
            self.read_evidence == "haos_seven_once"
            and self.semantic_evidence == "app_correlated_not_simultaneous"
            and self.key in ("fan_duty_supply", "fan_duty_extract")
        )


# These are the twelve actual raw signed int16 values reported by the earlier
# authorized one-shot RPC45 read, in the source candidate inventory order.
# No device identifier, account data or new RPC occurs here.
OBSERVED_CANDIDATE_RAW = (
    0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10,
)
BASELINE_ADDRESSES = (20, 21, 22, 23, 26)
CANDIDATE_ADDRESSES = (24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50)
SEVEN_ADDRESSES = BASELINE_ADDRESSES + (18, 19)


def decode_candidate_raw_batch(raw: Sequence[int]) -> dict[str, int]:
    """Strict 12-value read decoder; intentionally *no* physical-unit scaling.

    Preserve a raw zero as zero, never reinterpret it as 'off', 'no alarm',
    'not installed' or a physically meaningful -30 C.
    """
    candidates = list_source_only_candidates()
    if tuple(item.address for item in candidates) != CANDIDATE_ADDRESSES:
        raise EvidenceError("Unexpected candidate address order")
    if type(raw) not in (tuple, list) or len(raw) != len(candidates):
        raise EvidenceError("Unexpected candidate batch length")
    if any(type(item) is not int or not -32768 <= item <= 32767 for item in raw):
        raise EvidenceError("Invalid candidate raw int16 value")
    return {spec.key: value for spec, value in zip(candidates, raw)}


def inventory() -> tuple[RegisterEvidence, ...]:
    """Return the complete, fixed source-grounded 17-register evidence ledger."""
    if OPTIMA_270.read_rpc_id != 45:
        raise EvidenceError("Unexpected read RPC")
    base = tuple(
        RegisterEvidence(
            entry.key, entry.object_id, entry.address,
            "haos_five_active", "baseline_validated", None,
        )
        for entry in OPTIMA_270.readings
    )
    candidates = list_source_only_candidates()
    if (
        tuple(item.address for item in candidates) != CANDIDATE_ADDRESSES
        or len(OBSERVED_CANDIDATE_RAW) != len(candidates)
    ):
        raise EvidenceError("Unexpected candidate evidence shape")
    fan_keys = frozenset(("fan_duty_supply", "fan_duty_extract"))
    # A read of these two was also observed in the seven-item HAOS/QEMU
    # batch. Their scale matches a prior (non-concurrent) official UI view.
    additions = tuple(
        RegisterEvidence(
            entry.key, entry.object_id, entry.address,
            "haos_seven_once" if entry.key in fan_keys
            else "steamdeck_twelve_once",
            "app_correlated_not_simultaneous" if entry.key in fan_keys
            else "source_only_unverified",
            raw_value,
        )
        for entry, raw_value in zip(candidates, OBSERVED_CANDIDATE_RAW)
    )
    result = base + additions
    keys = [entry.key for entry in result]
    addresses = [(entry.object_id, entry.address) for entry in result]
    if (
        len(result) != 17
        or len(set(keys)) != 17
        or len(set(addresses)) != 17
        or tuple(item.address for item in base) != BASELINE_ADDRESSES
        or tuple(item.address for item in result if item.candidate_for_fan_projection)
        != (18, 19)
        or any(item.object_id != 0 for item in result)
    ):
        raise EvidenceError("Optima 270 register evidence mismatch")
    return result


def proposed_entity_keys(*, include_unreleased_fan_pair: bool = False) -> tuple[str, ...]:
    """Return five stable keys, or seven offline candidates with explicit opt-in.

    This is not a runtime read plan or Home Assistant entity setup. The
    optional pair requires a later live UI/HAOS release gate.
    """
    if type(include_unreleased_fan_pair) is not bool:
        raise EvidenceError("Fan projection gate must be boolean")
    entries = inventory()
    keys = tuple(entry.key for entry in entries if entry.ready_for_ha)
    if include_unreleased_fan_pair:
        keys += tuple(
            entry.key for entry in entries if entry.candidate_for_fan_projection
        )
    return keys
