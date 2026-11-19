#!/command/with-contenv bashio
set -u

QEMU="/usr/local/bin/qemu-x86_64-static"
SYSROOT="/opt/x86_64-sysroot"
NABTO="/opt/nabto/nabto-cli"

run_nabto() {
    "${QEMU}" -L "${SYSROOT}" "${NABTO}" "$@"
}

bashio::log.info "Genvex Nabto runtime test starting"
bashio::log.info "Native app architecture: $(uname -m)"

bashio::log.info "QEMU version:"
"${QEMU}" --version

bashio::log.info "Static ELF inspection report:"
if [ -r /opt/nabto/elf-report.txt ]; then
    cat /opt/nabto/elf-report.txt
else
    bashio::log.warning "ELF inspection report is missing"
fi

bashio::log.info "Checking the official Nabto 4 Client SDK version under x86-64 emulation"
if run_nabto -v; then
    bashio::log.info "PASS: Nabto CLI/SDK version command completed"
else
    result=$?
    bashio::log.error "FAIL: Nabto CLI/SDK version command exited with status ${result}"
fi

bashio::log.info "Requesting Nabto CLI help (read-only; no network or credentials)"
if run_nabto --help; then
    bashio::log.info "PASS: Nabto CLI help command completed"
else
    result=$?
    bashio::log.error "FAIL: Nabto CLI help command exited with status ${result}"
fi

bashio::log.info "Diagnostic completed. No certificate was created and no Genvex/Nabto device was contacted."
bashio::log.info "App will remain idle so its logs can be inspected."
exec sleep infinity
