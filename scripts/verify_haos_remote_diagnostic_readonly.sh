#!/bin/sh
# Safe only AFTER the separate Genvex Remote App has been explicitly installed
# and started with diagnostic_only=true and EMPTY credentials.
# No App installation, Docker changes, credentials, files, or Nabto requests.
set -eu

APP="app_local_genvex_nabto_remote"
echo "===== HAOS SYNTHETIC-ONLY APP ACCEPTANCE ====="

if ! docker inspect --type container "$APP" >/dev/null 2>&1; then
  echo "NOT READY: New experimental App container is not installed."
  exit 2
fi

running=$(docker inspect --type container "$APP" --format '{{.State.Running}}')
mode=$(docker inspect --type container "$APP" --format '{{.HostConfig.NetworkMode}}')
ports=$(docker inspect --type container "$APP" --format '{{json .HostConfig.PortBindings}}')
on_hassio=$(docker inspect --type container "$APP" --format '{{if index .NetworkSettings.Networks "hassio"}}yes{{else}}no{{end}}')

if [ "$running" != "true" ]; then
  echo "NOT READY: Experimental App is not running."
  exit 2
fi
if [ "$mode" = "host" ]; then
  echo "FAIL: Experimental App must not use host networking."
  exit 1
fi
if [ "$ports" != "{}" ] && [ "$ports" != "null" ]; then
  echo "FAIL: Experimental App has published host ports."
  exit 1
fi
if [ "$on_hassio" != "yes" ]; then
  echo "FAIL: Experimental App is not attached to the Supervisor hassio network."
  exit 1
fi

echo "PASS: experimental App running without host network or published host ports"
echo "PASS: experimental App attached to hassio network"

# -B prevents bytecode file creation in the existing Core container.
# -i is required so the source is consumed from stdin, not from a host file.
# No Authorization header is sent and redirects are NOT followed.
docker exec -i homeassistant python3 -B - <<'PY'
import http.client
import json

HOST = "local-genvex-nabto-remote"
PORT = 18275
EXPECTED = {
    "supply_air": 20.0, "outdoor_air": 5.0,
    "exhaust_air": 24.0, "extract_air": 22.0,
    "humidity": 50.0,
}

def check(path: str, status_expected: int) -> dict:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        response = conn.getresponse()
        if response.status != status_expected:
            raise RuntimeError("Unexpected diagnostic endpoint HTTP status")
        if response.getheader("Content-Type") != "application/json":
            raise RuntimeError("Unexpected diagnostic endpoint content type")
        length = response.getheader("Content-Length")
        if length is not None and int(length) > 2048:
            raise RuntimeError("Oversize diagnostic response")
        body = response.read(2049)
        if len(body) > 2048:
            raise RuntimeError("Oversize diagnostic response")
        document = json.loads(body)
        if not isinstance(document, dict):
            raise RuntimeError("Invalid diagnostic JSON")
        return document
    finally:
        conn.close()

try:
    doc = check("/v1/diagnostic", 200)
    if (
        doc.get("mode") != "DIAGNOSTIC_ONLY"
        or doc.get("synthetic") is not True
        or doc.get("notice") != "NOT_REAL_SENSOR_DATA"
        or doc.get("values") != EXPECTED
    ):
        raise RuntimeError("Unexpected synthetic-only diagnostic payload")
    if any(name in doc for name in ("schema_version", "device_id", "timestamp_utc", "health")):
        raise RuntimeError("Diagnostic response resembles a live snapshot")
    print("PASS: Core resolves dedicated App hostname and retrieves synthetic diagnostic")
    if check("/v1/snapshot", 404) != {"error": "not_found"}:
        raise RuntimeError("Production snapshot path unexpectedly reachable")
    print("PASS: production snapshot endpoint is disabled in diagnostic-only mode")
except Exception:
    # Do not leak URLs, response contents or internal network details.
    raise SystemExit("FAIL: Core-to-App diagnostic acceptance failed") from None

print("PASS: no real readings, Nabto credentials, or bearer token used")
PY
echo "===== ACCEPTANCE COMPLETE ====="
