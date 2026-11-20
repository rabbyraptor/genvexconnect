# Genvex Remote — development HAOS App candidate

**NOT YET APPROVED FOR INSTALLATION.** This source-only App candidate is
separate from the existing Genvex LAN integration and from the working Nabto
test App. Do not replace either.

## Purpose

Native ARM64 Python starts read-only, serial RPC45 polls through a legacy
x86_64 Nabto 4 SDK under QEMU. It publishes a five-sensor snapshot only on
the internal App Docker network, at port 18275. There is no host port mapping
and no device-control RPC. The App is configured to start manually.

## Configuration design (subject to security review)

App options: 12-digit device ID, Nabto profile identity, existing encrypted
private-key unlock passphrase, a random 43-character-or-longer IPC bearer
token, and a polling interval of at least 60 seconds. The passphrase and
token are marked as `password` fields in Supervisor options. This is not a
dedicated secret vault. Do not put secrets in logs, shell history, or Git.

The prototype reads **only** these pre-existing profile files from
`/share/genvex-remote-profile`: `client.crt` and
`client-encrypted.key`. It copies them to App-private `/data/profile` with
0600 permissions and does not overwrite the user's existing source profile.
The original private host profile path used in earlier tests is **not**
automatically mounted or moved. Profile onboarding and migration without a
terminal remain to be implemented.

The matching HA integration endpoint is
`http://app_local_genvex_nabto_remote:18275/v1/snapshot`. It requires the
same IPC bearer token. The endpoint must be reachable **only** over the
Supervisor-private App network; there is no TLS on this development-only
transport. Never publish port 18275 on a host/router.

## Installation blockers

- The build reuses the official Nabto CLI v1.3.0 download and legacy SDK
  extraction from the existing test App; third-party redistribution/license
  review is still pending.
- This new App image has **not been built or started on HAOS**.
- The private network and App DNS endpoint have **not been verified live**.
- A 60-second live polling soak test, restart test, and HA Core UI/entity test
  have not been completed.
- Secure, terminal-free profile enrollment/migration and safe token generation
  need a final UX. Manual token entry is development-only.
- A separate HA integration distribution package is required; the existing
  root `custom_components/genvexconnect` LAN integration must remain untouched.

Source is staged for code review and offline preflight only.
