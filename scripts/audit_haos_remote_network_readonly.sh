#!/bin/sh
# READ ONLY. No container starts, network changes, filesystem writes or secrets.
# Run only when an operator explicitly chooses to inspect HAOS.
set -eu

echo "===== HAOS DOCKER NETWORK READ-ONLY AUDIT ====="
echo "Docker server version:"
docker version --format '{{.Server.Version}}'
echo "Docker root directory:"
docker info --format '{{.DockerRootDir}}'

echo
echo "===== EXPECTED CONTAINERS ====="
# These are fixed expected names, not dynamic host data.
for name in homeassistant hassio_supervisor app_local_genvex_nabto_runtime_test app_local_genvex_nabto_remote; do
  if docker inspect --type container "$name" >/dev/null 2>&1; then
    echo "Container: $name (present)"
    docker inspect --type container "$name" \
      --format '  Running={{.State.Running}} NetworkMode={{.HostConfig.NetworkMode}} Privileged={{.HostConfig.Privileged}}'
    docker inspect --type container "$name" \
      --format '  PublishedPortBindings={{json .HostConfig.PortBindings}}'
    docker inspect --type container "$name" \
      --format '{{range $name, $settings := .NetworkSettings.Networks}}  Network={{$name}}{{println}}{{end}}'
  else
    echo "Container: $name (not present)"
  fi
done

echo
echo "===== STANDARD NETWORKS ====="
for name in hassio bridge host none; do
  if docker network inspect "$name" >/dev/null 2>&1; then
    echo "Network: $name"
    docker network inspect "$name" \
      --format '  Driver={{.Driver}} Internal={{.Internal}} Attachable={{.Attachable}}'
  else
    echo "Network: $name (not present)"
  fi
done

echo
echo "===== IMPORTED DEV IMAGE (IF PRESENT) ====="
if docker image inspect genvex-nabto-remote:ci >/dev/null 2>&1; then
  docker image inspect genvex-nabto-remote:ci \
    --format '  Architecture={{.Architecture}} OS={{.Os}} HAType={{index .Config.Labels "io.hass.type"}}'
else
  echo "Development image not present"
fi

echo
echo "===== AUDIT COMPLETE: READ-ONLY ====="
echo "No container, network, App or credential was modified."
