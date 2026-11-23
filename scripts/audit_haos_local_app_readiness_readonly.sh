#!/bin/sh
# Operator-side, read-only HAOS preflight BEFORE installing a new local App.
# Never modifies App folders, Docker state or Supervisor settings.
# Never reads configuration files, secrets, tokens, network addresses or logs.
set -eu

echo "===== HAOS LOCAL APP READ-ONLY INSTALL PREFLIGHT ====="
echo "Host architecture: $(uname -m)"
if command -v ha >/dev/null 2>&1; then
  echo "Home Assistant CLI: present"
else
  echo "Home Assistant CLI: missing (manual review required)"
fi

echo
echo "===== POSSIBLE LOCAL APP SOURCE DIRECTORIES ====="
for p in /mnt/data/supervisor/apps/local /mnt/data/supervisor/apps /mnt/data/supervisor/addons/local /mnt/data/supervisor/addons /addons/local /local_apps; do
  if [ -d "$p" ]; then
    echo "$p : PRESENT"
  else
    echo "$p : NOT_PRESENT"
  fi
done

echo
echo "===== SUPERVISOR PRIVATE DATA LOCATION (SOURCE PATH ONLY) ====="
docker inspect --type container hassio_supervisor --format '{{range .Mounts}}{{if eq .Destination "/data"}}Supervisor /data source: {{.Source}}{{println}}{{end}}{{end}}'

echo "===== TARGET APP EXISTS? ====="
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  echo "New experimental App container: PRESENT (do not overwrite)"
else
  echo "New experimental App container: NOT_INSTALLED"
fi
if docker inspect --type container app_local_genvex_nabto_runtime_test >/dev/null 2>&1; then
  echo "Existing Nabto runtime test App: PRESENT (must remain untouched)"
else
  echo "Existing Nabto runtime test App: NOT_PRESENT"
fi

echo
echo "===== TESTED IMAGE PRESENT? ====="
if docker image inspect genvex-nabto-remote:ci >/dev/null 2>&1; then
  docker image inspect genvex-nabto-remote:ci \
    --format 'Image: imported, Architecture={{.Architecture}} HAType={{index .Config.Labels "io.hass.type"}}'
else
  echo "Previous development image: NOT_PRESENT"
fi

echo
echo "===== FREE STORAGE AND MEMORY (NO PRIVATE FILE DATA) ====="
df -Pk /mnt/data | awk 'NR == 2 { print "Free disk space (KiB): " $4 }'
awk '/^MemAvailable:/ { print "Available RAM (KiB): " $2 }' /proc/meminfo

echo "===== READ-ONLY PREFLIGHT COMPLETE ====="
