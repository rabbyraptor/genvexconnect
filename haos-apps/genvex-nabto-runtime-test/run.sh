#!/command/with-contenv bashio
set -u

bashio::log.info "Genvex Nabto runtime test starting"
bashio::log.info "Native app architecture: $(uname -m)"
bashio::log.info "QEMU version:"
/usr/local/bin/qemu-x86_64-static --version

bashio::log.info "Checking the official Nabto 4 CLI under x86-64 emulation"
if /usr/local/bin/qemu-x86_64-static \
    -L /opt/x86_64-sysroot \
    /opt/nabto/nabto-cli -v; then
    bashio::log.info "PASS: official Nabto CLI started successfully under QEMU"
else
    result=$?
    bashio::log.error "FAIL: Nabto CLI exited with status ${result}"
    bashio::log.error "Review the build/runtime output above. No Genvex connection was attempted."
fi

bashio::log.info "Diagnostic completed. App will remain idle so its logs can be inspected."
exec sleep infinity
