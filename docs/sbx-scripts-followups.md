# Follow-ups from the sbx script consolidation

Deferred findings from the task and whole-branch reviews of
`feat/consolidate-sbx-scripts`. Most surfaced only on first real use against a
live `sbx`, which could not be installed in the original development
environment.

Resolved on 2026-08-29, verified against a live `sbx` (daemon v0.39.0) on
Linux. Items left open are recorded at the end with the reason.

## Correctness — done

- **`sbx_setup.py` now has a `require_tool` guard.** `do_secret_gh` checks for
  `gh` and `sbx`, and `do_install` checks the per-platform installer tools
  (`curl`/`sudo`, `winget`, or `brew`) before shelling out, so a missing tool
  gives an actionable message instead of a bare `FileNotFoundError`.
- **Negative return codes are normalised.** Both scripts route their exit
  through `normalise_exit`, mapping a signalled child's `-N` to `128 + N`
  (SIGTERM `-15` -> `143`, not the `241` that `sys.exit(-15)` produced).
  Verified with a real signalled child.
- **Both `__main__` guards catch `KeyboardInterrupt`** and exit `130` quietly
  instead of printing a traceback.
- **`cmd_stop` no longer masks a failed `sbx stop`.** `rm` still always runs,
  but the stop failure wins the exit code (`rc = rc or rm_rc`).
- **`ensure_mcp_registered` honours `sbx mcp add`'s exit code**, exiting
  (normalised) on failure rather than letting it surface later as an obscure
  `--static-mcp` error.

## Verified against a live `sbx` — done

- **MCP membership test tightened.** Replaced the `mcp in out.split()` token
  match over `sbx mcp ls` with `sbx mcp inspect <name>`, which exits `0` iff the
  server is registered — an exact per-server check with no false-positive risk.
  Confirmed: `inspect mslearn` -> `0`, `inspect zzz-nope` -> `1`.
- **`--mcp` with `--mode ssh`/`vscode` is valid.** `sbx create --help` lists
  `--static-mcp`; both `create` and `run` accept it. No change needed.
- **The kit path without a trailing slash works.** A real
  `sbx create --kit .../claude-custom claude .` succeeded and `sbx inspect`
  recorded the kit. The bash scripts' trailing slash was cosmetic.
- **The `sbx inspect` workspace probe was broken and is fixed.** The code
  parsed JSON but called `sbx inspect NAME`, whose default output is
  human-readable text, so the probe always returned `None` and fell through to
  the `sbx exec` probe (which needs a running sandbox). Now passes `--json`;
  the `workspace` key the parser already knew is present. On Linux this returns
  the host path, which equals the sandbox path; on Windows the host form fails
  the `startswith("/")` check and correctly falls through to the exec probe.

## Cosmetic — done

- **The cleanup hint is now platform-aware.** `invocation_prefix()` prints
  `./sbx_run.py` on POSIX and `uv run sbx_run.py` on Windows.

## Left open, by design

- **`scripts/31_docker_sbx_claude_custom_kit_bash.sh` assigns `REPO_ROOT` but
  never uses it.** The bash scripts are frozen; the variable is assigned but not
  read, so `set -u` is unaffected. Left in place.
- **Git recorded `31_..._bash.sh` as delete+create rather than a rename**
  (small file, similarity below git's default threshold). History is reachable
  with `git log --follow -M20% -- scripts/31_docker_sbx_claude_custom_kit_bash.sh`.
- **Spec drift:** the spec's File-layout table names `tests/test_sbx.py`, but the
  branch ships `tests/test_sbx_run.py` and `tests/test_sbx_setup.py`. The split
  is the better arrangement; the spec line is stale.
