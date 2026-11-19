#!/command/with-contenv bashio
set -u
umask 077

QEMU="/usr/local/bin/qemu-x86_64-static"
SYSROOT="/opt/x86_64-sysroot"
NABTO="/opt/nabto/nabto-cli"

TEST_HOME="$(mktemp -d /tmp/genvex-nabto-test.XXXXXX)"
CERT_OUTPUT="$(mktemp /tmp/genvex-nabto-certs.XXXXXX)"
DISCOVERY_OUTPUT="$(mktemp /tmp/genvex-nabto-discovery.XXXXXX)"

cleanup() {
    rm -rf "$TEST_HOME"
    rm -f "$CERT_OUTPUT" "$DISCOVERY_OUTPUT"
}
trap cleanup EXIT

run_nabto() {
    "${QEMU}" -L "${SYSROOT}" "${NABTO}" "$@"
}

bashio::log.info "Genvex Nabto runtime test v0.3.0 starting"
bashio::log.info "Native app architecture: $(uname -m)"

bashio::log.info "QEMU version:"
"${QEMU}" --version

bashio::log.info "Static ELF inspection report:"
if [ -r /opt/nabto/elf-report.txt ]; then
    cat /opt/nabto/elf-report.txt
else
    bashio::log.warning "ELF inspection report is missing"
fi

bashio::log.info "Test home directory created; existing Nabto user data will not be read"
bashio::log.info "Checking Nabto SDK startup and version"
if run_nabto --home-dir "$TEST_HOME" --version; then
    bashio::log.info "PASS: Nabto SDK startup, static-resource installation and version API completed"
else
    result=$?
    bashio::log.error "FAIL: Nabto startup/version check exited with status ${result}"
fi

bashio::log.info "Checking read-only certificate-store enumeration in isolated empty home"
if run_nabto --home-dir "$TEST_HOME" --certs >"$CERT_OUTPUT" 2>&1; then
    bashio::log.info "PASS: Nabto certificate enumeration API completed"
    bashio::log.info "Certificate names and fingerprints are intentionally suppressed"
else
    result=$?
    bashio::log.warning "Certificate enumeration returned status ${result}; output suppressed"
fi

bashio::log.info "Checking local Nabto discovery over QEMU networking (read-only)"
if timeout 25s "${QEMU}" -L "${SYSROOT}" "${NABTO}" --home-dir "$TEST_HOME" --discover >"$DISCOVERY_OUTPUT" 2>&1; then
    discovery_lines="$(awk 'END { print NR+0 }' "$DISCOVERY_OUTPUT")"
    bashio::log.info "PASS: Nabto discovery command completed; output lines: ${discovery_lines}"
    bashio::log.info "Discovered device identifiers and all raw output are intentionally suppressed"
else
    result=$?
    if [ "$result" -eq 124 ]; then
        bashio::log.warning "Nabto discovery exceeded the 25-second test limit"
    else
        bashio::log.warning "Nabto discovery returned status ${result}; raw output suppressed"
    fi
fi

bashio::log.info "Diagnostic completed. No certificate was created, no profile was opened, and no RPC/tunnel/control request was sent."
bashio::log.info "The discovery check is local-network-only; it does not attempt remote Genvex access."
bashio::log.info "App will remain idle so its logs can be inspected."
sleep infinity
