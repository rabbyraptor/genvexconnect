# Stage 1: Native ARM64 tools and the statically linked QEMU user emulator.
# This stage runs natively on the HAOS host architecture.
FROM debian:bookworm-slim AS tools

ARG NABTO_CLI_VERSION=1.3.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        file \
        qemu-user-static \
        unzip \
        binutils \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /tmp/nabto /opt/nabto; \
    curl --fail --location --retry 3 \
      "https://github.com/nabto/nabto-cli/releases/download/v${NABTO_CLI_VERSION}/nabto-cli-linux.zip" \
      -o /tmp/nabto-cli-linux.zip; \
    unzip -q /tmp/nabto-cli-linux.zip -d /tmp/nabto; \
    CLI="$(find /tmp/nabto -type f -name nabto-cli -print -quit)"; \
    SDK="$(find /tmp/nabto -type f -name libnabto_client_api.so -print -quit)"; \
    test -n "${CLI}"; \
    test -n "${SDK}"; \
    install -m 0755 "${CLI}" /opt/nabto/nabto-cli; \
    install -m 0644 "${SDK}" /opt/nabto/libnabto_client_api.so; \
    readelf -h /opt/nabto/nabto-cli | grep -q 'Advanced Micro Devices X86-64'; \
    readelf -h /opt/nabto/libnabto_client_api.so | grep -q 'Advanced Micro Devices X86-64'; \
    { \
      echo "Nabto CLI release: ${NABTO_CLI_VERSION}"; \
      echo "=== CLI file type ==="; \
      file /opt/nabto/nabto-cli; \
      echo "=== CLI ELF interpreter ==="; \
      readelf -l /opt/nabto/nabto-cli | grep 'Requesting program interpreter' || true; \
      echo "=== CLI shared-library dependencies ==="; \
      readelf -d /opt/nabto/nabto-cli | grep NEEDED || true; \
      echo "=== Nabto SDK file type ==="; \
      file /opt/nabto/libnabto_client_api.so; \
      echo "=== Nabto SDK shared-library dependencies ==="; \
      readelf -d /opt/nabto/libnabto_client_api.so | grep NEEDED || true; \
    } > /opt/nabto/elf-report.txt; \
    test -x /usr/bin/qemu-x86_64-static

# Stage 2: Ubuntu 24.04 x86-64 runtime libraries.
# No commands are executed in this foreign-architecture stage; BuildKit only
# copies its filesystem into the final ARM64 image.
FROM --platform=linux/amd64 ubuntu:24.04 AS x86sysroot

# Stage 2B: a pre-built Python x86-64 runtime (no foreign-arch RUN).
# The Ubuntu sysroot still provides glibc and SDK dependencies as before.
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS x86python

# Stage 3: Native ARM64 Home Assistant app.
FROM ghcr.io/home-assistant/base:3.24

ARG BUILD_ARCH
ARG BUILD_VERSION

# Native ARM64 certificate-enrollment prerequisites. Kept separate from the
# verified x86_64 Nabto SDK under QEMU. No live enrollment or key creation.
RUN apk add --no-cache python3 py3-cryptography openssl ca-certificates \
    && python3 -c 'import cryptography; from cryptography import x509; print("PASS: native cryptography")' \
    && openssl version >/dev/null

COPY --from=tools /usr/bin/qemu-x86_64-static /usr/local/bin/qemu-x86_64-static
COPY --from=tools /opt/nabto/ /opt/nabto/
COPY --from=x86sysroot /lib/x86_64-linux-gnu/ /opt/x86_64-sysroot/lib/x86_64-linux-gnu/
COPY --from=x86sysroot /lib64/ld-linux-x86-64.so.2 /opt/x86_64-sysroot/lib64/ld-linux-x86-64.so.2
COPY --from=x86sysroot /usr/lib/x86_64-linux-gnu/ /opt/x86_64-sysroot/usr/lib/x86_64-linux-gnu/
COPY --from=x86python /usr/local/bin/python3.12 /opt/x86_64-sysroot/usr/local/bin/python3
COPY --from=x86python /usr/local/lib/python3.12/ /opt/x86_64-sysroot/usr/local/lib/python3.12/
COPY --from=x86python /usr/local/lib/libpython3.12.so.1.0 /opt/x86_64-sysroot/usr/local/lib/libpython3.12.so.1.0
COPY --from=x86python /usr/lib/x86_64-linux-gnu/libffi.so.8* /opt/x86_64-sysroot/usr/lib/x86_64-linux-gnu/
COPY --from=x86python /usr/lib/x86_64-linux-gnu/libexpat.so.1* /opt/x86_64-sysroot/usr/lib/x86_64-linux-gnu/

COPY probe_remote_batch.py /opt/nabto/probe_remote_batch.py
COPY run.sh /run.sh
RUN chmod 0755 /run.sh \
    && /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot /opt/nabto/nabto-cli -v \
    && /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib /opt/x86_64-sysroot/usr/local/bin/python3 -c 'import ctypes, json, urllib.parse; print("x86_64 Python ctypes OK")'

LABEL \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.version="${BUILD_VERSION}"

CMD ["/run.sh"]
