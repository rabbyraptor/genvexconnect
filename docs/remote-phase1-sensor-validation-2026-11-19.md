# Phase 1 — source-grounded read-only Optima 270 sensor validation

Date: 2026-11-19  
Branch: `remote-nabto-connection`  
**Current state: PHASE 1 + PHASE 1B COMPLETE on Linux x86_64 Steam Deck — five individual read-only RPC 45 calls and one five-item RPC batch successful. HAOS/QEMU still pending.**

## Baseline and success criterion

The project already independently verified SDK 4.9.11 remote `ping.json` / ID 17 on x86_64 and on HAOS ARM64/QEMU, and a first single-sensor `candidate_read_datapoints.json` **RPC ID 45** on Steam Deck. The latter returned `raw=367`, decoded `6.7 °C` for the supply-air sensor (obj=0, address=20). Official Genvex Connect iOS app showed `Supply air: 6.70 °C` in a user-provided screenshot. See [verified facts](remote-nabto-verified-facts.md).

The next milestone is **read-only, address-specific multi-sensor coverage**, without yet using a multi-element RPC batch or any control/write operation. Each sensor is requested separately to isolate errors. A later distinct milestone will test batching only after individual reads have been validated.

## Phase 1 test matrix (all source-derived, not guessed)

All operations use the already-verified RPC **ID 45**, a single list entry `obj=0`, `trailer=1`, and one response `int16`. Scale/offset is from [public Optima 270 model](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py):

| Read | Address | Conversion | Original app screenshot at 22:33 | Live independent test |
| --- | ---: | --- | ---: | --- |
| Supply air | 20 | (raw - 300)/10 °C | 6.70 °C | **VERIFIED** 367 -> 6.70 °C |
| Outdoor air | 21 | (raw - 300)/10 °C | 0.20 °C | **VERIFIED READ** 299 -> -0.10 °C |
| Exhaust air | 22 | (raw - 300)/10 °C | 1.80 °C | **VERIFIED READ** 313 -> 1.30 °C |
| Extract air | 23 | (raw - 300)/10 °C | 7.60 °C | **VERIFIED READ** 376 -> 7.60 °C |
| Humidity | 26 | raw % | 66 % | **VERIFIED READ** 66 -> 66 % |

App readings are **historical snapshots**, not exact expected values at future test times. Temperatures can change between captures; compare contemporaneously. If a sensor produces an invalid/out-of-range result, do not auto-correct or infer a different query layout. Stop and inspect safely.

## Artifacts

- [`scripts/probe_remote_sensors_phase1.py`](../scripts/probe_remote_sensors_phase1.py): five individual RPC 45 calls **maximum**, with known addresses only; aborts at first failed RPC/decoding error. Uses the pre-existing x86_64 SDK and encrypted test profile. Suppresses account, host, key, passphrase, raw JSON and full URLs.
- [`tests/test_remote_sensors_phase1.py`](../tests/test_remote_sensors_phase1.py): static offline checks for the five addresses, single read-only RPC ID 45, and list/response types.
- Earlier one-sensor working reference: [`scripts/probe_remote_datapoint45_readonly.py`](../scripts/probe_remote_datapoint45_readonly.py).

Before committing the plan, a separate locally constructed phase-1 prototype passed **six offline tests** for URL JSON, five-address mapping, XML shape, normal/invalid responses and sanitized error events. The user has subsequently executed the committed phase-1 test file successfully on the authorized device; results are documented below. These prototype tests are not a substitute for executing the repo's static test suite and the live gateway probe.

## Running in existing Linux x86_64 Steam Deck environment

Use the same existing account identity and device hostname as earlier tests **without pasting them in chat or committing them**. Set them interactively (the read prompts below keep identity out of shell history, although the script receives them as environment variables):

```bash
umask 077
SCRIPT=$(mktemp /tmp/genvex-phase1.XXXXXX.py) || exit 1
curl -fsSL 'https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts/probe_remote_sensors_phase1.py' -o "$SCRIPT" || { rm -f "$SCRIPT"; exit 1; }
read -r -p "Nabto identity (email): " GENVEX_NABTO_IDENTITY
read -r -p "Gateway hostname: " GENVEX_NABTO_HOST
GENVEX_NABTO_IDENTITY="$GENVEX_NABTO_IDENTITY" GENVEX_NABTO_HOST="$GENVEX_NABTO_HOST" timeout -k 5s 75s python3 "$SCRIPT"
STATUS=$?
rm -f "$SCRIPT"
unset GENVEX_NABTO_IDENTITY GENVEX_NABTO_HOST
echo "Test exit status: $STATUS"
```

The current script exits nonzero for incomplete sensor coverage. As always, also inspect its `Read-only sensors decoded: 5/5` line. On failure it stops further read RPCs and prints only sanitized diagnostics.

## Gate to proceed

- SDK startup, session, XML registration each succeed.
- Five one-element calls return status 0 and decode one signed integer each.
- App or local HA comparison is consistent with the model's measurement scales at approximately the same time.
- Document exact **source-defined** address, conversion, sanitized observed data, and any failure.
- Only then add a *separate* test for batching or test RPC 45 on HAOS ARM64/QEMU.
- Do not change existing local Home Assistant integration or use query ID 43/write functions.

## Executed phase 1: five individual sensor readings (2026-11-19)

**USER-VERIFIED on Steam Deck x86_64, official Nabto 4 Client SDK 4.9.11, authenticated remote gateway.** All startup/resources/profile/XML statuses were **0**. Exactly five sequential source-defined read-only RPC-ID-45 requests, each for one item with obj=0, trailer=1, completed and decoded. No write operations or changes to the existing Home Assistant integration.

| Label | Address | Raw int16 | Converted value | Observed RPC elapsed time |
| --- | ---: | ---: | ---: | ---: |
| Supply air | 20 | 365 | 6.50 °C | 335 ms |
| Outdoor air | 21 | 299 | -0.10 °C | 17 ms |
| Exhaust air | 22 | 313 | 1.30 °C | 16 ms |
| Extract air | 23 | 376 | 7.60 °C | 16 ms |
| Humidity | 26 | 66 | 66 % | 16 ms |

End-of-run summary: `Read-only sensors decoded: 5/5`; session closed 0, SDK shutdown 0, temporary profile cleaned up, shell exit 0. Times are individual SDK invocation durations in a single run, **not** a latency distribution, guaranteed speed or independent measurement of transport route. The first call may include on-demand connection setup, but that is not separately measured.

Earlier official iOS screenshot at **22:33** reported supply 6.70 °C, outdoor 0.20 °C, exhaust 1.80 °C, extract 7.60 °C and humidity 66 %. The two identical values and plausible small temperature changes are useful corroboration, but do not prove strict synchrony for the other measurements.

**Outcome:** Phase 1 individual read-only sensor coverage **passed on Steam Deck**. Next gate: run an isolated single multi-item **read-only** RPC-ID-45 batch for the same five source-defined addresses; verify response count/order/mapping and device behavior. Only after batch verification should HAOS/QEMU and integration work proceed. Native ARM64 SDK, certified binary redistribution and production resilience remain open.

## Phase 1B: successful five-element batch

The newly prepared [`scripts/probe_remote_sensors_batch_phase1b.py`](../scripts/probe_remote_sensors_batch_phase1b.py) performs **one** authorized, read-only RPC 45 request containing five list entries in exactly the source-documented order `20,21,22,23,26`, with one `obj=0` per entry and trailer 1. The proposed response schema is the same list of signed 16-bit values already verified in single-element form. The probe verifies that the response list contains **exactly five** values, then associates each response position to its requested address. It does not send writes, scan addresses, or log sensitive account/device data; failure yields a nonzero exit code. Static checks: [`tests/test_remote_sensor_batch_phase1b.py`](../tests/test_remote_sensor_batch_phase1b.py).

**UPDATED AFTER USER TEST:** batch capability is now verified for exactly these five addresses and this request order; other sizes, permutations and HAOS/QEMU execution are untested.

### Phase 1B — verified read-only RPC 45 five-element batch (2026-11-19)

**VERIFIED from user's Steam Deck terminal output:** same existing authenticated x86_64 Nabto SDK 4.9.11 test profile, with explicit passphrase via stdin. `nabtoStartup`, `nabtoInstallDefaultStaticResources`, `nabtoOpenSession` and `nabtoRpcSetDefaultInterface` all returned **0**. Exactly one `nabtoRpcInvoke` for query **45** with the ordered five-item request `obj=0`, addresses **20, 21, 22, 23, 26**, trailer=1, returned **RPC status 0** in **318 ms**. Its response decoded to **five signed int16 values**:

| Address | Sensor | Raw | Converted |
| ---: | --- | ---: | ---: |
| 20 | Supply air | 365 | 6.50 °C |
| 21 | Outdoor air | 299 | -0.10 °C |
| 22 | Exhaust air | 313 | 1.30 °C |
| 23 | Extract air | 377 | 7.70 °C |
| 26 | Humidity | 65 | 65 % |

Log ended `Read-only batch decoded: 5/5`, `Result: BATCH_DECODED`, session close 0, SDK shutdown 0, cleaned temporary profile and wrapper success. This demonstrates **one working five-address remote batch**, including response count and values consistent with individual reads and expected position ordering. Since no response-side address IDs were present, response **ordering is strongly corroborated rather than independently proven for every possible list**. An additional repeated/reordered batch could check this if needed. The 318 ms is one observed elapsed time and not a latency benchmark.

**Now next gate:** run the same read-only batch inside the **existing isolated** HAOS Raspberry Pi 4 ARM64/QEMU test runtime. Do not change the working Home Assistant integration, commit private credentials or SDK binaries, or enable writes. Confirm SDK/CLI invocation and response decoding in the emulated environment; only then plan HA entity mapping and runtime deployment.

