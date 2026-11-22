# Development MCP tool preflight (not deployed)

**Status:** source-only candidate; the running DEV5 MCP service is still
read-only with four verified tools. This PR does not install a server, add
MCP endpoints, change the Docker socket mount or restart any HAOS container.

## Proposed staged capabilities

- `runtime_file_patch`: `preview_runtime_patch` validates one of 13 fixed
  Python filenames, an exact previous SHA-256, bounded UTF-8 source, syntax
  and a regular non-symlink source file. **It does not write**. Future
  authenticated patch transport must add a separately reviewed atomic write,
  verification and rollback procedure before it can become a real MCP tool.
- `runtime_test`: `run_allowlisted_offline_test` runs only hard-coded unittest
  selectors without a shell. It returns exit status and test count, not raw
  output. Before exposing this remotely, execute it in a separate
  unprivileged, no-network, no-secret container with hard CPU/memory limits.
- `container_restart` and `dev_deploy`: **not implemented or enabled**.
  These need separate approval and deployment state gates, not generic shell
  commands exposed to the assistant.

The current MCP server resides in a host-managed Docker volume rather than
this repository; its installed source has not been modified by this PR.

## Offline checks

```sh
python3 -m unittest discover -s tools/haos_dev_mcp -p 'test_*.py' -v
python3 -m compileall -q tools/haos_dev_mcp
```

The test fixture exercises SHA race rejection, symlink/path traversal,
invalid replacement source, success/failure of a fixed fake unittest suite,
and absence of raw test errors from returned results. CI uses a dedicated
workflow. No actual SDK, account, Docker socket or HAOS API is needed.

## Activation gate

1. Review patch policy, sandboxing and CI results.
2. Port only approved functions into a separately permissioned MCP service.
3. Add an explicit authorization or operator approval boundary for every
   write/deploy operation; verify backup and rollback.
4. Test installed tools end-to-end before raising the autonomy level.
