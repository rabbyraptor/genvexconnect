#!/command/with-contenv bashio
set -eu
umask 077
exec python3 -u /opt/genvex-remote/runtime/app_bootstrap.py
