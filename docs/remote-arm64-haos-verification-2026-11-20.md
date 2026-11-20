# ARM64 HAOS runtime verification and next remote connection gate

Verified by user on HAOS Raspberry Pi 4 (2026-11-20):

- GitHub Actions native ARM64 image build passed its metadata and offline Python-import checks.
- Downloaded `genvex-nabto-remote-arm64.tar.gz` passed `sha256sum -c SHA256SUMS`; compressed artifact ~99 MB.
- Steam Deck rootless Podman loaded the image, reporting `Architecture=arm64`, `OS=linux`, `io.hass.type=app`, `io.hass.arch=aarch64`, and image size ~267 MB.
- HAOS Docker loaded `genvex-nabto-remote:ci`, and offline native ARM64 Python imports passed with `--network none --read-only`.
- Under QEMU, x86_64 Python passed with exit code 0.
- Nabto CLI `-v` returned `4.9.11` with exit code 0 on a disposable writable container filesystem. With `--read-only` and `--tmpfs /root/.nabto:rw,nosuid,nodev,size=32m,mode=0700`, the CLI again returned `4.9.11` and the expected profile files appeared, including `logs/nabto-api-log.txt`, `nabto_config.ini`, roots and guest identity files.
- A diagnostic `find -printf` command failed because the HAOS base image uses BusyBox. A subsequent BusyBox-compatible `find -print` test succeeded and verified the log file.

These tests **do not establish remote connectivity or validate a live RPC45 call in this image**. No App installation, live credentials, host networking, or changes to the working LAN integration were involved.

## Source review

- `genvex-nabto-remote/runtime/sdk_snapshot_adapter.py` launches the x86_64 Python probe under `qemu-x86_64-static` and passes identity, host, and unlock secret over stdin. Its subprocess environment sets `HOME=/tmp` and `GENVEX_NABTO_PROFILE` to a supplied private profile directory.
- `probe_remote_snapshot.py` invokes SDK `nabtoStartup(tmp)` using a disposable directory, copies the existing encrypted key and certificate into its temporary `users/` directory, and performs one read-only RPC45 batch. Thus the CLI's default `/root/.nabto` profile behavior is not proof that the probe requires that location; the two paths must be tested independently.
- `app_bootstrap.py` currently copies certificate/key from `/share/genvex-remote-profile/` to `/data/profile/`. This shared import path is an unresolved private-key exposure concern and must not be recommended for a real App installation.
- The HTTP snapshot bridge binds to container interfaces and uses a bearer token. Before enabling, verify Supervisor private networking, absence of host port publication, and token provisioning.
- The default App entrypoint expects `/data/options.json` and an authorized profile; running the default entrypoint is not an offline smoke test.

## Next acceptance gates

1. Perform additional **offline, credential-free** verification of SDK probe prerequisites and isolation. Do not run the App entrypoint or request a real gateway connection yet.
2. Design and test App-private enrollment or a controlled import into `/data`, avoiding `/share` and avoiding any alteration of the existing host profile.
3. Validate the App-to-HA private transport and secret-safe token provisioning.
4. Only after those gates, ask the user to authorize a bounded live read-only RPC45 attempt. Never ask the user to paste credentials or private keys into chat.
5. Test restart persistence, failure/recovery and Home Assistant integration lifecycle before recommending installation.

The working LAN integration remains untouched. The ARM64 image is a development artifact, not a production-ready HAOS App.

## Security hardening staged after ARM64 validation

On the development branch, the separate App bootstrap was changed to **reject**
missing or insecure private profile material rather than importing private
keys from globally shared `/share`. `config.yaml` no longer grants the App
`share:ro`. The App requires pre-provisioned `/data/profile/client.crt` and
`/data/profile/client-encrypted.key`, a mode-0700 directory, and private
regular PEM files with no group/other permissions. Symbolic-link inputs are
rejected. The offline test suite now checks this behavior with fake data,
including symlinks and insecure permissions.

**Status: source changes committed, CI results not yet independently
verified.** The already-loaded `genvex-nabto-remote:ci` image on HAOS is
from the earlier build; none of these changes are present in that image.
Do not install or start the App with real secrets yet. No secure App-private
profile provisioning or enrollment UX has been implemented.

## Staged one-time offline profile provisioner

Added `genvex-nabto-remote/runtime/profile_provision.py` as a **development-only,
not-yet-integrated** helper. It accepts two bounded length-prefixed PEM values
from standard input: a certificate and an **encrypted** private key. It never
places credentials in command-line arguments, environment variables, GitHub
artifacts or logs. It rejects pre-existing App-private profiles and writes
new profile files with owner-only permissions inside `/data/profile`,
using a temporary staging directory. The working LAN profile is neither read
nor modified. New source tests use only fake PEM strings and cover length
limits, invalid envelopes, truncation, trailing data, symlinks, permissions,
and no-overwrite behavior.

This helper **does not solve enrollment, identity verification, secure delivery
of the stdin stream to the App-private volume, or Supervisor lifecycle
integration**. It is deliberately not invoked by the App's default entrypoint.
Never forward actual keys through GitHub, chat, shell history or `/share`.
A separate reviewed operator-side procedure and security acceptance tests
are required before any live provisioning.

The new GitHub Actions offline checks are **not yet confirmed** for these
latest commits; do not treat their existence as proof of a pass.

## Integrated offline profile handoff checks

App bootstrap validation now requires **exact** PEM envelope types: X.509
`CERTIFICATE` and `ENCRYPTED PRIVATE KEY` (not merely any `BEGIN` header),
plus bounded private regular files. Provisioner tests now directly call App
bootstrap's validator to verify the entire fake-profile handoff, and assert
that swapped file types or an unencrypted key are rejected.

These changes are development-source-only. The earlier successful offline
workflow run covers the preceding provisioning tests; these **new integration
tests have not yet been confirmed passed in CI**. The previously imported HAOS
image has not been rebuilt, and no secret provisioning has been attempted.

## Internal bearer-token endpoint hardening

The Home Assistant read-only client now restricts its bearer-token destination
to the **exact** expected Supervisor App endpoint
`http://app_local_genvex_nabto_remote:18275/v1/snapshot`.
Previously, it accepted arbitrary private IPs and `app_*` hostnames, which
could route the token to unintended peers if misconfigured. Regression tests
now reject other App hostnames, private IPs, lookalike domains and URL
fragments. Redirect following remains disabled and the HTTP response remains
bounded.

The offline App workflow has been amended to trigger on
`experimental/home_assistant/**` and run the HA fake-transport/snapshot
tests, instead of only compiling App sources and testing App bootstrap.

**Remaining network security gates:** Exact URL checks are not sufficient to
prove that Supervisor DNS and App network boundaries isolate the endpoint.
Verify the actual private namespace, absence of published host ports,
reachable peers, and lifecycle in a controlled HAOS test. Plain HTTP bearer
tokens require a trusted isolated network; no real token should be used before
that is verified. These latest changes are not yet independently verified in
GitHub Actions.
