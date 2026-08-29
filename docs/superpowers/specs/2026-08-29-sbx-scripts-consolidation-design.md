# Consolidating the sbx helper scripts into cross-platform Python

Date: 2026-08-29
Status: Approved for planning

## Problem

The repository ships ten bash helper scripts (`00_`–`33_`) that wrap the
`sbx` CLI. They are bash-only, so they do not run on Windows, where `sbx`
is natively supported. They are also a copy-paste matrix rather than a
collection: eight of the ten are the same two orthogonal axes — kit and
attach-mode — duplicated across files.

The duplication has already produced a defect.
`31_docker_sbx_claude_custom_kit_bash.sh` execs into a sandbox named
`claude-custom`, but `30_docker_sbx_claude_custom_kit.sh` creates one
named `claude-custom-kit`. The two names were edited independently and
drifted, so the bash script has never attached to anything.

Cleanup handling is likewise inconsistent mid-refactor: scripts 20, 21 and
30 prompt interactively with `read -r -p`, while 22, 23, 32 and 33 print
manual-stop instructions in comments.

Because the bash scripts are retained (see Migration), the matrix
duplication that produced the `30`/`31` defect survives in bash by design.
Freezing them at current feature parity is what bounds that risk: the
instance is fixed, and no new modes are added there to drift again.

## Goals

- One entry point per lifecycle, running natively on Linux, macOS and
  Windows.
- Eliminate the kit × mode duplication *in the Python interface*, so that
  adding a kit or a mode there is a single edit.
- Fix the `30`/`31` name mismatch structurally, not by hand.
- Unify cleanup on the manual direction chosen in commit `a275cf2`.
- Keep the bash scripts working, moved out of the repository root.

## Non-goals

- Changing `sbx-kits/`. The `claude-custom` kit is untouched.
- Packaging for PyPI. See "Invocation" for why `uvx` is out of scope.
- Supporting agents other than `claude`.
- Rewriting the bash scripts. They are moved, their paths fixed and the
  `30`/`31` mismatch corrected; their structure is left alone.
- Backporting future work to bash. The bash scripts are frozen at today's
  feature parity. A new mode or kit is added to the Python scripts only.
  "Kept working" means they continue to do what they do now, not that they
  track the Python interface.

## Platform findings

`sbx` runs natively on Windows 11 (`winget install -h Docker.sbx`,
Windows Hypervisor Platform required) — there is a real `sbx.exe` and no
WSL2 requirement. It is also supported on Ubuntu 24.04+ (KVM, `kvm` group)
and macOS 14+ on Apple silicon. "Windows compatible" therefore cannot mean
"a bash script"; it means the launcher must run under a Windows-native
interpreter.

## Language and invocation

Python, as a single-file script per lifecycle, with PEP 723 inline
metadata and `uv` supplying the interpreter:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
```

Invocation differs only in the shebang:

| Platform | Command |
| --- | --- |
| Linux, macOS | `./sbx_run.py --mode ssh` |
| Windows | `uv run sbx_run.py --mode ssh` |

Windows has no shebang mechanism, so Windows users invoke `uv run`
explicitly. Both forms are documented in the README.

`uvx` is not a supported invocation. `uvx` is `uv tool run`: it executes
packages from an index or a git URL, not local PEP 723 files. The scripts
are inherently repo-local regardless — every kit-using invocation passes
`--kit ./sbx-kits/claude-custom/`, a path inside this repository — so the
scripts are run from the repository root.

**Dependencies: none.** `argparse`, `subprocess`, `shutil`, `sys` and
`pathlib` cover the whole surface. `uv` makes dependencies cheap but not
free; each one is a first-run download imposed on a script whose entire job
is to launch something else quickly.

## File layout

Two scripts, split by lifecycle:

| Path | Scope |
| --- | --- |
| `sbx_setup.py` | One-time host bootstrap: platform-gated install, GitHub secret. |
| `sbx_run.py` | The kit × mode matrix, plus `stop`. |
| `scripts/*.sh` | The ten original bash scripts, kept working. |
| `tests/test_sbx.py` | Unit tests for the pure functions. |
| `docs/superpowers/specs/` | This document. |
| `sbx-kits/claude-custom/` | Unchanged. |

The Python scripts stay at the repository root as the primary entry point.
The bash scripts move into `scripts/`, which both unclutters the root and
signals which interface is current without deleting anything.

Underscores rather than hyphens in the filenames so that `tests/` can
import the pure functions directly; a hyphenated filename requires
`importlib` indirection to import.

The two scripts share roughly twenty mechanical lines (locating `sbx`,
`run_interactive`, dry-run printing). This duplication is accepted
deliberately. A shared `_common.py` would cost each script its
self-contained property — as written, either file can be copied elsewhere
and run standalone under `uv`. Revisit if the shared surface grows
substantially beyond twenty lines.

## `sbx_run.py`

### Interface

```
./sbx_run.py                     # kit=claude-custom, mode=run (defaults)
./sbx_run.py --no-kit            # plain claude agent, no kit
./sbx_run.py --mode ssh          # create, setup ssh, ssh in
./sbx_run.py --mode vscode       # create, setup ssh, code --remote
./sbx_run.py --mode bash         # sbx exec -it <name> bash
./sbx_run.py --mcp mslearn       # add and attach an MCP server
./sbx_run.py --name my-sandbox   # override the derived name
./sbx_run.py --workspace ~/proj  # mount some other directory
./sbx_run.py --dry-run           # print commands instead of running them
./sbx_run.py stop [--rm]         # stop, optionally remove
```

Defaults are `--mode run` with the `claude-custom` kit, because that is the
common case (`30_docker_sbx_claude_custom_kit.sh` today).

`run` and `stop` are a single optional positional argument
(`nargs="?"`, `choices=["run", "stop"]`, `default="run"`) rather than
`argparse` subparsers. Subparsers cannot express "no subcommand means
`run`", and a bare `./sbx_run.py` is the most frequent invocation. The
consequence is that both commands share one flag namespace: `stop` accepts
`--mode`, `--no-kit`, `--name` and `--mcp` so that it can derive the same
name the corresponding `run` produced, and ignores the rest.

### Internal structure

Four layers, so that the logic worth testing has no I/O in it:

| Layer | Responsibility |
| --- | --- |
| naming | `(kit, mode) -> str`. Pure. |
| argv building | `(name, kit, mcp, workspace, mode) -> list[str]`. Pure. |
| process | `run_interactive()`, `run_capture()`. All I/O. |
| commands | `cmd_run`, `cmd_stop`. Orchestration only. |

Keeping naming and argv-building pure is what allows the behaviour to be
verified on a machine with no working `sbx` installation.

### Name derivation

```
name = ("claude"
        + ("-custom" if kit else "")
        + ("-mcp" if mcp else "")
        + MODE_SUFFIX[mode])

MODE_SUFFIX = {"run": "", "bash": "", "ssh": "-ssh", "vscode": "-vscode"}
```

The `-mcp` segment keeps an MCP-attached sandbox distinct from a plain one
that would otherwise derive the same name, matching the separate
`claude-mcp` sandbox that script `21` creates today.

`bash` deliberately shares `run`'s suffix, so it attaches to the sandbox
that `--mode run` created. That is what script `31` was intended to do.
Deriving both names from one expression makes them agree by construction,
which is the structural fix for the drift described in Problem.

`ssh` and `vscode` keep distinct names because those sandboxes persist
across invocations, whereas `run`-mode sandboxes are ephemeral. This
preserves current behaviour.

`--name` overrides the derived value for ad-hoc use.

### Mode behaviour

| Mode | Sequence |
| --- | --- |
| `run` | `sbx run --name <n> [--kit ...] [--static-mcp ...] claude <cwd>` |
| `bash` | `sbx exec -it <n> bash` |
| `ssh` | `ensure_created`, `sbx setup ssh --alias <n>.sbx`, `ssh -t <n>.sbx "cd <sandbox_path>; bash --login"` |
| `vscode` | `ensure_created`, `sbx setup ssh --alias <n>.sbx`, `code --remote ssh-remote+<n>.sbx <sandbox_path>` |

`--mcp <name>` registers the server before the run and passes
`--static-mcp <name>`. The Microsoft Learn server
(`https://learn.microsoft.com/api/mcp`) ships as a known name so that
`--mcp mslearn` works without a URL; any other value requires `--mcp-url`.

Registration must be idempotent. `sbx mcp add` on an already-registered
name fails, so a second `./sbx_run.py --mcp mslearn` would abort — script
`21` only avoids this by never having been run twice under `set -e`. The
script checks `sbx mcp ls` first and skips `add` when the name is already
present. (`21` already calls `sbx mcp ls`, so the listing is available.)

Note one divergence to confirm on first run: script `21` writes
`sbx run claude --name ... --static-mcp ...`, with the agent before the
flags, while `20` and `30` write `sbx run --name ... claude`, with the
agent after. The canonical form follows the majority — flags first, agent
last, workspace final.

`ensure_created` is idempotent: it captures the output of `sbx create` and
treats an "already exists" message as success, re-raising anything else.
This is the pattern scripts 22, 23, 32 and 33 already use.

### TTY handling

This is the constraint most likely to break the rewrite. `sbx run claude`
is a full-screen TUI; `ssh -t`, `sbx exec -it bash` and `code --remote` all
need the real terminal.

- `run_interactive(argv)` calls `subprocess.run(argv)` with stdin, stdout
  and stderr **inherited**. No `capture_output`, no pipes, no
  `shell=True`. The child's exit code propagates to the caller.
- `run_capture(argv)` is used in exactly one place: the `ensure_created`
  "already exists" probe. That command is non-interactive, so capturing is
  safe.

These are two separate functions rather than one function with a flag,
because confusing them is the difference between a working launcher and a
hung terminal.

### Sandbox-side workspace path

`ssh -t <host> "cd <path>; bash --login"` needs the path *inside* the
sandbox. The current scripts pass `$(pwd)`, the host path, which works only
because host and sandbox paths coincide on Linux. On Windows the host path
is `C:\Users\...`, which is not the mount point.

The host path itself needs no translation: `Path` already yields the native
form that `sbx` and `sbx.exe` expect, `C:\Users\...` included. This is a
direct benefit of choosing Python over bash-plus-`cygpath`.

The sandbox path is resolved at runtime, first match wins:

1. `sbx inspect <name>`, parsing the workspace mount. This is structured
   host-side data and needs no running sandbox.
2. `sbx exec <name> sh -c 'echo $WORKSPACE_DIR'`.
3. The host path, as today.

`sbx inspect` is tried first despite `spec.yaml` referencing
`WORKSPACE_DIR`, for two reasons. That reference is in a *startup command*,
where the runtime injects the variable — which is not evidence it is
exported into an arbitrary `sbx exec` shell. And `sbx exec` requires a
*running* sandbox, whereas `--mode ssh` reaches the probe immediately after
`sbx create`, which may not have started it.

The probe is unverified at design time because `sbx` is not installable in
the authoring environment. The fallback chain makes an incorrect first
guess non-fatal; confirm which branch fires on the first real run and
simplify if warranted.

### Workspace resolution

The mounted workspace defaults to the **repository root**, resolved from
the script's own location rather than from the invocation directory:

```python
REPO_ROOT = Path(__file__).resolve().parent          # sbx_run.py sits at the root
```

```bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # scripts/*.sh
```

Deriving from the script location rather than `$(pwd)` or a literal
`$(pwd)/..` means both interfaces mount the same directory no matter where
they are invoked from. A literal `$(pwd)/..` in `scripts/` would be correct
only when the caller has already `cd`-ed into `scripts/`, and would mount
the repository's *parent* when run from the root — which is the more
natural invocation.

This is a deliberate change from the current behaviour, where the scripts
mount `$(pwd)`, whatever that happens to be. Pinning to the repository root
makes the two interfaces agree and matches how the scripts are actually
used: sandboxing work on this repository's kits. `--workspace <path>` on
`sbx_run.py` restores the ability to sandbox an arbitrary directory;
`--workspace .` reproduces the old behaviour exactly.

The kit path is resolved the same way — `REPO_ROOT / "sbx-kits" /
"claude-custom"` in Python, `"$REPO_ROOT/sbx-kits/claude-custom/"` in bash
— so the relative `./sbx-kits/...` in the current scripts becomes
location-independent rather than merely gaining a `../`.

### Cleanup

Unified on the manual direction taken in commit `a275cf2`. No `read -p`
prompts anywhere. After an interactive session ends, the script prints the
exact command to clean up:

```
Sandbox 'claude-custom-ssh' is still running. To remove it:
  ./sbx_run.py stop --rm --mode ssh
```

`stop` without `--rm` runs `sbx stop <name>`; with `--rm` it also runs
`sbx rm <name> --force`. It gives the Python interface a first-class
equivalent of the manual-stop comment blocks in scripts 22, 23, 32 and 33,
which those scripts keep.

## `sbx_setup.py`

### Interface

```
uv run sbx_setup.py                      # install sbx for this platform
uv run sbx_setup.py --secret-gh          # gh auth token -> sbx secret set github
uv run sbx_setup.py --dry-run            # print what it would do
uv run sbx_setup.py --platform windows   # force a platform (testing)
```

`--secret-gh` lives here rather than in `sbx_run.py` because storing a
GitHub token is one-time host configuration with the same lifecycle as the
install. It is a flag rather than a subcommand because installing and
storing the secret are the only two things this script does.

### Platform gating

Dispatched on `sys.platform`, overridable with `--platform`:

| Platform | Sequence |
| --- | --- |
| Linux | `curl -fsSL https://get.docker.com \| sudo REPO_ONLY=1 sh`; `sudo apt-get install docker-sbx`; `sudo usermod -aG kvm $USER`; `sbx login` |
| Windows | Check Windows Hypervisor Platform; `winget install -h Docker.sbx`; `sbx login` |
| macOS | `brew trust docker/tap`; `brew install docker/tap/sbx`; `sbx login` |

An unrecognised platform exits with a clear message rather than guessing.

The current `00_docker_sbx_setup.sh` calls `newgrp kvm`. This cannot work
from a subprocess — `newgrp` spawns a replacement shell that exits
immediately, leaving the parent's group membership unchanged. The script
prints the log-out-and-back-in instruction instead of executing something
that appears to work and does not.

The same inherited-stdio rule from `sbx_run.py` applies here, and matters
more: `sudo apt-get` prompts for a password, `sbx login` is interactive,
and `winget install` writes progress to the console. Capturing any of these
hangs the script on an invisible prompt. Every command in this script uses
`run_interactive`; nothing is captured.

The `curl | sudo sh` step is emitted as a shell pipeline via
`subprocess.run(..., shell=True)`. This is the one place `shell=True` is
acceptable: the command is a fixed literal with no interpolated input. It
is still interactive — `sudo` prompts — so its stdio is inherited like
everything else.

## Error handling

- `sbx` missing from `PATH`: detected via `shutil.which("sbx")`, with a
  message pointing at `sbx_setup.py`. Checked once at startup.
- `code` missing: `shutil.which("code")` before `--mode vscode`, with a
  message naming the Remote-SSH extension requirement. On Windows the
  executable is `code.cmd`, which `shutil.which` resolves via `PATHEXT`;
  a bare `subprocess.run(["code", ...])` would raise `FileNotFoundError`.
- Any `sbx` invocation failing: exit code propagated unchanged, so the
  scripts compose in CI and shell pipelines.
- `--mode bash` against a non-existent sandbox: `sbx exec` fails on its
  own; its message is passed through rather than wrapped.

## Testing

`--dry-run` prints the exact command lines instead of executing them. It is
useful on its own and is the seam the tests use.

`tests/test_sbx.py`, stdlib `unittest`, no pytest dependency. Run with:

```
python3 -m unittest discover -s tests -t .
```

`-t .` is required: without it, `discover` treats `tests/` as the top-level
directory, leaving the repository root off `sys.path` so `import sbx_run`
fails — which would defeat the point of the underscore filenames. The tests
are stdlib-only, so plain `python3` is used; there is no dependency for
`uv run` to resolve.

Coverage:

- Name derivation for all eight kit × mode combinations, including an
  explicit assertion that `run` and `bash` derive the same name — the
  regression test for the `30`/`31` defect.
- Argv construction for each mode, with and without `--kit` and `--mcp`.
- `--name` overriding the derived value.
- `sbx_setup.py --dry-run --platform {linux,windows,darwin}` emitting the
  right command sequence for each, verifiable from a Linux host.
- Workspace resolution defaulting to the repository root, and `--workspace`
  overriding it.
- The kit path resolving under the repository root rather than the
  invocation directory — asserted by running `--dry-run` from a different
  working directory.

Not covered by automated tests: TTY inheritance and the `WORKSPACE_DIR`
probe, both of which require a real `sbx` installation. Verify manually on
first run.

## Migration

All ten `.sh` files move from the repository root into `scripts/`, using
`git mv` so history follows them. They are **kept working**, not frozen:

- The `--kit` argument becomes `"$REPO_ROOT/sbx-kits/claude-custom/"`, with
  `REPO_ROOT` derived as shown in "Workspace resolution". A bare `../` would
  work only from inside `scripts/`.
- The workspace argument becomes `"$REPO_ROOT"` in place of `"$(pwd)"`.
- `31_docker_sbx_claude_custom_kit_bash.sh` is corrected to exec into
  `claude-custom-kit`, the name `30` actually creates. The defect is fixed
  in both interfaces, not just the Python one.
- The bash scripts keep their existing sandbox names. Renaming them to match
  the Python derivation would break anyone's running sandboxes for no gain,
  since the two interfaces are not meant to share sandboxes.

The README's Quick start block still names the moved files:

```console
$ ./00_docker_sbx_setup.sh
$ ./30_docker_sbx_claude_custom_kit.sh
```

Both paths break on the move, so Quick start becomes `uv run sbx_setup.py`
followed by `./sbx_run.py`. The existing script table gains a `scripts/`
prefix and is preceded by the new Python command table, with this
equivalence mapping:

| Bash script (in `scripts/`) | Python equivalent |
| --- | --- |
| `00_docker_sbx_setup.sh` | `uv run sbx_setup.py` |
| `10_docker_sbx_secret_gh.sh` | `uv run sbx_setup.py --secret-gh` |
| `20_docker_sbx_claude_nokit.sh` | `./sbx_run.py --no-kit` |
| `21_docker_sbx_claude_mcp.sh` | `./sbx_run.py --no-kit --mcp mslearn` (sandbox `claude-mcp`) |
| `22_docker_sbx_claude_ssh.sh` | `./sbx_run.py --no-kit --mode ssh` |
| `23_docker_sbx_claude_ssh_vscode.sh` | `./sbx_run.py --no-kit --mode vscode` |
| `30_docker_sbx_claude_custom_kit.sh` | `./sbx_run.py` |
| `31_docker_sbx_claude_custom_kit_bash.sh` | `./sbx_run.py --mode bash` |
| `32_docker_sbx_claude_custom_kit_ssh.sh` | `./sbx_run.py --mode ssh` |
| `33_docker_sbx_claude_custom_kit_ssh_vscode.sh` | `./sbx_run.py --mode vscode` |

The README also gains `uv` as a prerequisite, the Windows invocation form,
and a note that the bash scripts remain available for hosts without `uv`.

Because nothing is deleted, this migration is reversible: the Python
scripts can be removed and `scripts/` moved back with no loss.

### Orphaned sandboxes

Four of the Python-derived names differ from the ones the bash scripts use.
Since the bash scripts keep their names, the two interfaces create separate
sandboxes for the same scenario. That is intentional — they can be run side
by side without interfering — but it means switching to the Python scripts
leaves the old sandboxes running. Listing with `sbx ls` and removing them by
hand is a one-time cleanup:

| Bash sandbox | Python sandbox |
| --- | --- |
| `claude-nokit` | `claude` |
| `claude-custom-kit` | `claude-custom` |
| `claude-ssh-vscode` | `claude-vscode` |
| `claude-custom-ssh-vscode` | `claude-custom-vscode` |

`claude-mcp`, `claude-ssh` and `claude-custom-ssh` keep their names.

## Open items

The `WORKSPACE_DIR` probe (see "Sandbox-side workspace path") is the one
piece unverified at design time. It ships with the fallback chain and is
confirmed on first real run.
