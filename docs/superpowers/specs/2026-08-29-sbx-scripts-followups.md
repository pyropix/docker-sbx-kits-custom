# Follow-ups from the sbx script consolidation

Deferred findings from the task and whole-branch reviews of
`feat/consolidate-sbx-scripts`. None blocked the merge. Recorded here because
the review workspace that held them is deleted once the branch finishes.

Most of these surface only on first real use against a live `sbx`, which could
not be installed in the development environment.

## Correctness, worth doing

- **`sbx_setup.py` has no `require_tool` equivalent.** `sbx_run.py` locates
  `sbx` and `code` via `shutil.which` and exits with an actionable message.
  `sbx_setup.py` does not, so `--secret-gh` on a host without `gh` raises a
  bare `FileNotFoundError` traceback. The friendly "run `gh auth login` first"
  message only fires when `gh` exists but is unauthenticated. Same gap for a
  missing `sbx` or `brew`.
- **Negative return codes break exit-code propagation.** A child killed by a
  signal returns a negative code: `run_interactive(["bash","-c","kill -TERM $$"])`
  yields `-15`, and `sys.exit(-15)` produces shell status 241 rather than 143.
  Normalise with `128 + (-rc)` when negative.
- **Neither `__main__` guard catches `KeyboardInterrupt`**, so Ctrl-C during a
  sandbox TUI prints a traceback instead of exiting quietly.
- **`cmd_stop` overwrites `rc`**, so a failed `sbx stop` followed by a
  successful `sbx rm --force` exits 0.
- **`ensure_mcp_registered` ignores `sbx mcp add`'s exit code.** A failed
  registration surfaces later as an obscure `sbx run --static-mcp` failure.

## Unverified against a live `sbx`

- **`sbx mcp ls` membership test** uses `mcp in out.split()`, a token match over
  the whole listing including URLs and headers. A short or generic server name
  could false-positive and silently skip registration. Tighten once the real
  output format is known.
- **`--mcp` with `--mode ssh`/`vscode`** passes `--static-mcp` to `sbx create`.
  The spec's mode table only shows that flag for `sbx run`. Fails loudly if
  unsupported, so the risk is low.
- **The kit path loses its trailing slash** (`.../claude-custom` where the bash
  scripts pass `.../claude-custom/`). Almost certainly irrelevant, but it is an
  unverified divergence from the form known to work.
- **`sandbox_workspace_path` falls back to the host path** when both probes
  fail. Correct on Linux, where host and sandbox paths coincide; on Windows it
  would `cd` to a path that does not exist in the sandbox.

## Cosmetic

- **The cleanup hint always prints `./sbx_run.py ...`**, which is not the
  documented Windows invocation (`uv run sbx_run.py ...`).
- **`scripts/31_docker_sbx_claude_custom_kit_bash.sh` assigns `REPO_ROOT` but
  never uses it** — that script takes no path arguments. Left in place
  deliberately: the bash scripts are frozen, and the variable is assigned but
  not read, so `set -u` is unaffected.
- **Git recorded `31_..._bash.sh` as delete+create rather than a rename**
  (small file, similarity below git's default threshold). History is reachable
  with `git log --follow -M20% -- scripts/31_docker_sbx_claude_custom_kit_bash.sh`;
  plain `--follow` shows only the move commit.
- **Spec drift:** the spec's File-layout table names `tests/test_sbx.py`, but the
  branch ships `tests/test_sbx_run.py` and `tests/test_sbx_setup.py`. The split
  is the better arrangement; the spec line is stale.
