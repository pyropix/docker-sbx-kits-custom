# sbx Script Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ten copy-pasted bash helper scripts with two cross-platform Python scripts run under `uv`, keeping the bash scripts working in `scripts/` as a fallback.

**Architecture:** Two single-file PEP 723 scripts at the repository root. `sbx_run.py` dispatches over a kit × mode matrix, deriving the sandbox name from `(kit, mcp, mode)` so names cannot drift. `sbx_setup.py` handles one-time host bootstrap, gated on platform. Both separate pure logic (name derivation, argv building) from I/O (subprocess), so the interesting behaviour is unit-testable without a working `sbx` install.

**Tech Stack:** Python 3.11+ stdlib only (`argparse`, `subprocess`, `shutil`, `pathlib`, `json`, `unittest`). `uv` supplies the interpreter. No third-party dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-sbx-scripts-consolidation-design.md`

## Global Constraints

- **No third-party dependencies.** `dependencies = []` in every PEP 723 block. `uv` makes dependencies cheap but not free; each is a first-run download on a script whose job is to launch something else quickly.
- **`requires-python = ">=3.11"`** in every PEP 723 block.
- **Interactive commands must inherit stdio.** `subprocess.run(argv)` with no `capture_output`, no pipes, no `text=True`. `sbx run claude` is a full-screen TUI; `ssh -t`, `sbx exec -it`, `code --remote`, `sudo` and `sbx login` all need the real terminal. Capturing any of them hangs the script on an invisible prompt.
- **Capture only where explicitly specified.** Exactly three places capture: the `sbx create` "already exists" probe, the sandbox-workspace-path probe, and `gh auth token`. Everything else inherits.
- **`shell=True` is used exactly once:** the `curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh` pipeline in `sbx_setup.py`. It is a fixed literal with no interpolated input. Its stdio is still inherited, because `sudo` prompts.
- **Both scripts need `if __name__ == "__main__":` guards.** The tests `import sbx_run` and `import sbx_setup`; without the guard, importing executes `main()`.
- **Exit codes propagate unchanged** from `sbx` and friends, so the scripts compose in pipelines.
- **Company name is written lowercase** — "baramundi", "baramundi software" — anywhere it appears in prose.
- **Conventional commit format** for every commit (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- **The `sbx-kits/` directory is never modified.**
- **The bash scripts are frozen at current feature parity.** They are moved, their paths fixed and the `30`/`31` defect corrected. No new modes or flags are backported to them.

## Path anchoring (applies to Tasks 1–5)

Three anchors, deliberately different. Getting these confused is the most likely defect in this plan.

| What | Anchor |
| --- | --- |
| Python mounted workspace | `Path.cwd()`, overridable with `--workspace` |
| Python kit path | `Path(__file__).resolve().parent / "sbx-kits" / "claude-custom"` |
| Bash workspace **and** kit | `REPO_ROOT`, derived from `${BASH_SOURCE[0]}` |

The kit anchors to the script, not the workspace, so `./sbx_run.py` invoked from an unrelated project still finds the kit in *this* repository. `Path.cwd()` is read in the commands layer and passed into the pure argv builder as a parameter — never read inside the builder.

## File Structure

| Path | Responsibility | Task |
| --- | --- | --- |
| `sbx_run.py` | Kit × mode dispatcher, `stop` command. | 1, 2, 3 |
| `sbx_setup.py` | Platform-gated host bootstrap, GitHub secret. | 4 |
| `tests/__init__.py` | Empty. Makes `tests/` a package. | 1 |
| `tests/test_sbx_run.py` | Unit tests for `sbx_run.py` pure functions. | 1, 2, 3 |
| `tests/test_sbx_setup.py` | Unit tests for `sbx_setup.py` command building. | 4 |
| `scripts/*.sh` | The ten original bash scripts, moved and path-fixed. | 5 |
| `scripts/README.md` | Describes the bash scripts. | 6 |
| `README.md` | Describes the two Python scripts only. | 6 |

Tests run with `python3 -m unittest discover -s tests -t .` from the repository root. Two details, both verified by running the code in this plan:

- **`-t .` is required.** Without it, `discover` treats `tests/` as the top-level directory, leaving the repository root off `sys.path` so `import sbx_run` fails.
- **`tests/__init__.py` is required.** With `-t .`, the start directory must be importable. Without the file, `discover` aborts before running anything with `ImportError: Start directory is not importable: '.../tests'`. Task 1 creates it.

---

### Task 1: Pure core of `sbx_run.py` — name derivation and argv building

The pure functions, with no I/O. This is where the `30`/`31` defect is fixed structurally.

**Files:**
- Create: `sbx_run.py`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_sbx_run.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `MODE_SUFFIX: dict[str, str]`
  - `KNOWN_MCP: dict[str, str]`
  - `KIT_DIR: Path`
  - `derive_name(use_kit: bool, mcp: str | None, mode: str) -> str`
  - `build_sbx_argv(verb: str, name: str, kit: Path | None, mcp: str | None, workspace: Path) -> list[str]`
  - `build_exec_argv(name: str) -> list[str]`
  - `build_ssh_argv(name: str, sandbox_path: str) -> list[str]`
  - `build_vscode_argv(code_exe: str, name: str, sandbox_path: str) -> list[str]`
  - `alias_for(name: str) -> str`

- [ ] **Step 1: Make `tests/` an importable package**

```bash
mkdir -p tests
touch tests/__init__.py
```

Required by `unittest discover -s tests -t .`. Without it, discovery aborts with `ImportError: Start directory is not importable` before running a single test.

- [ ] **Step 2: Write the failing test**

Create `tests/test_sbx_run.py`:

```python
"""Unit tests for the pure functions in sbx_run.py."""

import unittest
from pathlib import Path

import sbx_run


class TestDeriveName(unittest.TestCase):
    def test_default_is_custom_kit_run_mode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "run"), "claude-custom")

    def test_no_kit_run_mode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "run"), "claude")

    def test_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(True, None, "ssh"), "claude-custom-ssh")

    def test_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "vscode"), "claude-custom-vscode")

    def test_no_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(False, None, "ssh"), "claude-ssh")

    def test_no_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "vscode"), "claude-vscode")

    def test_mcp_gets_its_own_segment(self):
        self.assertEqual(sbx_run.derive_name(False, "mslearn", "run"), "claude-mcp")

    def test_mcp_composes_with_kit_and_mode(self):
        self.assertEqual(
            sbx_run.derive_name(True, "mslearn", "ssh"), "claude-custom-mcp-ssh"
        )

    def test_bash_and_run_derive_the_same_name(self):
        """Regression test for the 30/31 defect.

        31_docker_sbx_claude_custom_kit_bash.sh exec'd into `claude-custom`
        while 30_docker_sbx_claude_custom_kit.sh created `claude-custom-kit`,
        so it never attached to anything. Deriving both from one expression
        makes them agree by construction.
        """
        for use_kit in (True, False):
            for mcp in (None, "mslearn"):
                self.assertEqual(
                    sbx_run.derive_name(use_kit, mcp, "bash"),
                    sbx_run.derive_name(use_kit, mcp, "run"),
                )

    def test_all_eight_kit_mode_combinations(self):
        expected = {
            (True, "run"): "claude-custom",
            (True, "bash"): "claude-custom",
            (True, "ssh"): "claude-custom-ssh",
            (True, "vscode"): "claude-custom-vscode",
            (False, "run"): "claude",
            (False, "bash"): "claude",
            (False, "ssh"): "claude-ssh",
            (False, "vscode"): "claude-vscode",
        }
        for (use_kit, mode), want in expected.items():
            with self.subTest(use_kit=use_kit, mode=mode):
                self.assertEqual(sbx_run.derive_name(use_kit, None, mode), want)


class TestBuildSbxArgv(unittest.TestCase):
    WORKSPACE = Path("/home/user/proj")

    def test_run_without_kit(self):
        self.assertEqual(
            sbx_run.build_sbx_argv("run", "claude", None, None, self.WORKSPACE),
            ["sbx", "run", "--name", "claude", "claude", "/home/user/proj"],
        )

    def test_run_with_kit(self):
        argv = sbx_run.build_sbx_argv(
            "run", "claude-custom", Path("/repo/sbx-kits/claude-custom"), None, self.WORKSPACE
        )
        self.assertEqual(
            argv,
            [
                "sbx", "run", "--name", "claude-custom",
                "--kit", "/repo/sbx-kits/claude-custom",
                "claude", "/home/user/proj",
            ],
        )

    def test_run_with_mcp(self):
        argv = sbx_run.build_sbx_argv("run", "claude-mcp", None, "mslearn", self.WORKSPACE)
        self.assertEqual(
            argv,
            [
                "sbx", "run", "--name", "claude-mcp",
                "--static-mcp", "mslearn",
                "claude", "/home/user/proj",
            ],
        )

    def test_create_verb(self):
        argv = sbx_run.build_sbx_argv("create", "claude-ssh", None, None, self.WORKSPACE)
        self.assertEqual(argv[:2], ["sbx", "create"])

    def test_flags_precede_agent_and_workspace_is_last(self):
        """Scripts 20 and 30 write `sbx run --name ... claude`; script 21 writes
        `sbx run claude --name ...`. The canonical form follows the majority."""
        argv = sbx_run.build_sbx_argv(
            "run", "n", Path("/k"), "mslearn", self.WORKSPACE
        )
        self.assertEqual(argv[-2:], ["claude", "/home/user/proj"])
        self.assertLess(argv.index("--name"), argv.index("claude"))

    def test_kit_path_is_stringified_not_a_path_object(self):
        argv = sbx_run.build_sbx_argv("run", "n", Path("/k"), None, self.WORKSPACE)
        for item in argv:
            self.assertIsInstance(item, str)


class TestOtherArgvBuilders(unittest.TestCase):
    def test_alias_appends_sbx_suffix(self):
        self.assertEqual(sbx_run.alias_for("claude-custom-ssh"), "claude-custom-ssh.sbx")

    def test_exec_argv(self):
        self.assertEqual(
            sbx_run.build_exec_argv("claude-custom"),
            ["sbx", "exec", "-it", "claude-custom", "bash"],
        )

    def test_ssh_argv(self):
        self.assertEqual(
            sbx_run.build_ssh_argv("claude-ssh", "/work/proj"),
            ["ssh", "-t", "claude-ssh.sbx", "cd /work/proj ; bash --login"],
        )

    def test_vscode_argv(self):
        self.assertEqual(
            sbx_run.build_vscode_argv("/usr/bin/code", "claude-vscode", "/work/proj"),
            ["/usr/bin/code", "--remote", "ssh-remote+claude-vscode.sbx", "/work/proj"],
        )


class TestKitDir(unittest.TestCase):
    def test_kit_dir_is_anchored_to_the_script_not_the_cwd(self):
        """`./sbx_run.py` run from an unrelated project must still find the kit
        in this repository."""
        expected = Path(sbx_run.__file__).resolve().parent / "sbx-kits" / "claude-custom"
        self.assertEqual(sbx_run.KIT_DIR, expected)
        self.assertTrue(sbx_run.KIT_DIR.is_absolute())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: `ModuleNotFoundError: No module named 'sbx_run'`.

- [ ] **Step 4: Write the minimal implementation**

Create `sbx_run.py`:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Launch Claude Code in a Docker Sandbox.

The sandbox name is derived from (kit, mcp, mode) rather than typed per
scenario, so the ten bash scripts this replaces cannot drift apart again.
"""

from pathlib import Path

# Mode -> sandbox-name suffix.
#
# `bash` deliberately shares `run`'s empty suffix: it attaches to the sandbox
# `--mode run` created. `ssh` and `vscode` get their own names because those
# sandboxes persist across invocations while run-mode sandboxes are ephemeral.
MODE_SUFFIX = {
    "run": "",
    "bash": "",
    "ssh": "-ssh",
    "vscode": "-vscode",
}

# MCP servers that can be named without also passing --mcp-url.
KNOWN_MCP = {
    "mslearn": "https://learn.microsoft.com/api/mcp",
}

# Anchored to this script, NOT to the workspace or the cwd, so the kit is
# found even when sbx_run.py is invoked from an unrelated project.
KIT_DIR = Path(__file__).resolve().parent / "sbx-kits" / "claude-custom"

AGENT = "claude"


def derive_name(use_kit: bool, mcp: str | None, mode: str) -> str:
    """Build the sandbox name from the axes that distinguish sandboxes."""
    return (
        "claude"
        + ("-custom" if use_kit else "")
        + ("-mcp" if mcp else "")
        + MODE_SUFFIX[mode]
    )


def alias_for(name: str) -> str:
    """The SSH host alias `sbx setup ssh` registers for a sandbox."""
    return f"{name}.sbx"


def build_sbx_argv(
    verb: str,
    name: str,
    kit: Path | None,
    mcp: str | None,
    workspace: Path,
) -> list[str]:
    """Build `sbx run` or `sbx create`: flags first, agent then workspace last."""
    argv = ["sbx", verb, "--name", name]
    if kit is not None:
        argv += ["--kit", str(kit)]
    if mcp:
        argv += ["--static-mcp", mcp]
    argv += [AGENT, str(workspace)]
    return argv


def build_exec_argv(name: str) -> list[str]:
    return ["sbx", "exec", "-it", name, "bash"]


def build_ssh_argv(name: str, sandbox_path: str) -> list[str]:
    return ["ssh", "-t", alias_for(name), f"cd {sandbox_path} ; bash --login"]


def build_vscode_argv(code_exe: str, name: str, sandbox_path: str) -> list[str]:
    return [code_exe, "--remote", f"ssh-remote+{alias_for(name)}", sandbox_path]
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add sbx_run.py tests/__init__.py tests/test_sbx_run.py
git commit -m "feat: add derived sandbox naming and argv building for sbx_run

Deriving the sandbox name from (kit, mcp, mode) fixes the 30/31 defect
structurally: 31 exec'd into claude-custom while 30 created
claude-custom-kit."
```

---

### Task 2: CLI, process layer, and the `run` and `bash` modes

Makes `sbx_run.py` executable end to end for the two modes that need no sandbox-path probe.

**Files:**
- Modify: `sbx_run.py`
- Modify: `tests/test_sbx_run.py`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces:
  - `build_parser() -> argparse.ArgumentParser`
  - `resolve_workspace(raw: str | None) -> Path`
  - `resolve_mcp(mcp: str | None, mcp_url: str | None) -> str | None`
  - `run_interactive(argv: list[str], dry_run: bool = False) -> int`
  - `run_capture(argv: list[str]) -> tuple[int, str]`
  - `require_tool(name: str, hint: str) -> str`
  - `cmd_run(args: argparse.Namespace) -> int`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sbx_run.py`, above the `if __name__` block:

```python
class TestResolveWorkspace(unittest.TestCase):
    def test_default_is_cwd(self):
        self.assertEqual(sbx_run.resolve_workspace(None), Path.cwd())

    def test_explicit_path_is_made_absolute(self):
        result = sbx_run.resolve_workspace("..")
        self.assertTrue(result.is_absolute())
        self.assertEqual(result, Path.cwd().parent.resolve())

    def test_tilde_is_expanded(self):
        result = sbx_run.resolve_workspace("~")
        self.assertEqual(result, Path.home().resolve())


class TestResolveMcp(unittest.TestCase):
    def test_none_when_not_requested(self):
        self.assertIsNone(sbx_run.resolve_mcp(None, None))

    def test_known_name_needs_no_url(self):
        self.assertEqual(sbx_run.resolve_mcp("mslearn", None), "mslearn")

    def test_unknown_name_without_url_is_an_error(self):
        with self.assertRaises(SystemExit):
            sbx_run.resolve_mcp("something-else", None)

    def test_unknown_name_with_url_is_accepted(self):
        self.assertEqual(
            sbx_run.resolve_mcp("custom", "https://example.test/mcp"), "custom"
        )


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = sbx_run.build_parser()

    def test_bare_invocation_defaults_to_run_with_the_kit(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.mode, "run")
        self.assertFalse(args.no_kit)

    def test_stop_is_a_positional_not_a_subparser(self):
        args = self.parser.parse_args(["stop", "--rm"])
        self.assertEqual(args.command, "stop")
        self.assertTrue(args.rm)

    def test_stop_accepts_the_name_deriving_flags(self):
        args = self.parser.parse_args(["stop", "--mode", "ssh", "--no-kit"])
        self.assertEqual(args.mode, "ssh")
        self.assertTrue(args.no_kit)

    def test_stop_accepts_but_ignores_workspace(self):
        """--workspace is meaningless for stop; it is silently ignored, not
        rejected, because run and stop share one flag namespace."""
        args = self.parser.parse_args(["stop", "--workspace", "/tmp"])
        self.assertEqual(args.command, "stop")

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--mode", "telepathy"])


class TestDryRun(unittest.TestCase):
    def test_dry_run_prints_and_does_not_execute(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.run_interactive(["definitely-not-a-real-binary"], dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("definitely-not-a-real-binary", buf.getvalue())

    def test_dry_run_of_run_mode_emits_the_full_command(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(["--dry-run", "--workspace", "/tmp/proj"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("sbx run --name claude-custom", out)
        self.assertIn(str(sbx_run.KIT_DIR), out)
        self.assertIn("/tmp/proj", out)

    def test_dry_run_kit_path_is_independent_of_the_workspace(self):
        """Regression guard: the kit must not be resolved relative to the
        mounted workspace."""
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--workspace", "/somewhere/unrelated"])
        self.assertIn(str(sbx_run.KIT_DIR), buf.getvalue())

    def test_dry_run_bash_mode_targets_the_run_sandbox(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--mode", "bash"])
        self.assertIn("sbx exec -it claude-custom bash", buf.getvalue())
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: FAIL with `AttributeError: module 'sbx_run' has no attribute 'resolve_workspace'`.

- [ ] **Step 3: Write the minimal implementation**

Add to the top of `sbx_run.py`, after the docstring:

```python
import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
```

Then append to `sbx_run.py`:

```python
def resolve_workspace(raw: str | None) -> Path:
    """The directory mounted into the sandbox.

    Defaults to the current working directory, preserving the behaviour of
    the bash scripts this replaces. Resolved to an absolute path so that a
    relative --workspace behaves predictably once handed to sbx.
    """
    if raw is None:
        return Path.cwd()
    return Path(raw).expanduser().resolve()


def resolve_mcp(mcp: str | None, mcp_url: str | None) -> str | None:
    """Validate the MCP selection, returning the server name or None."""
    if mcp is None:
        return None
    if mcp not in KNOWN_MCP and not mcp_url:
        sys.exit(
            f"error: unknown MCP server '{mcp}'. Pass --mcp-url, or use one of: "
            + ", ".join(sorted(KNOWN_MCP))
        )
    return mcp


def mcp_url_for(mcp: str, mcp_url: str | None) -> str:
    return mcp_url or KNOWN_MCP[mcp]


def render(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def run_interactive(argv: list[str], dry_run: bool = False) -> int:
    """Run a command with stdin/stdout/stderr inherited.

    Interactive by design: sbx run is a full-screen TUI, and ssh -t,
    sbx exec -it and code --remote all need the real terminal. Never
    capture here -- doing so hangs the script on an invisible prompt.
    """
    if dry_run:
        print(render(argv))
        return 0
    return subprocess.run(argv).returncode


def run_capture(argv: list[str]) -> tuple[int, str]:
    """Run a non-interactive command and capture its combined output.

    Used only for probes: the `sbx create` already-exists check and the
    sandbox workspace path lookup.
    """
    proc = subprocess.run(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    return proc.returncode, proc.stdout


def require_tool(name: str, hint: str) -> str:
    """Locate an executable or exit with an actionable message.

    shutil.which resolves code.cmd on Windows via PATHEXT, which a bare
    subprocess.run(["code", ...]) would not.
    """
    found = shutil.which(name)
    if found is None:
        sys.exit(f"error: '{name}' not found on PATH. {hint}")
    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sbx_run.py",
        description="Launch Claude Code in a Docker Sandbox.",
    )
    # A single optional positional rather than subparsers: subparsers cannot
    # express "no subcommand means run", and a bare ./sbx_run.py is the most
    # frequent invocation. The cost is one shared flag namespace.
    parser.add_argument(
        "command", nargs="?", choices=["run", "stop"], default="run"
    )
    parser.add_argument(
        "--mode", choices=sorted(MODE_SUFFIX), default="run",
        help="how to attach to the sandbox (default: run)",
    )
    parser.add_argument(
        "--no-kit", action="store_true", help="use the plain claude agent"
    )
    parser.add_argument("--mcp", help="MCP server to attach")
    parser.add_argument("--mcp-url", help="URL for an MCP server not in KNOWN_MCP")
    parser.add_argument("--name", help="override the derived sandbox name")
    parser.add_argument(
        "--workspace", help="directory to mount (default: current directory)"
    )
    parser.add_argument(
        "--rm", action="store_true", help="with stop: also remove the sandbox"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print commands instead of running them"
    )
    return parser


def sandbox_name(args: argparse.Namespace) -> str:
    return args.name or derive_name(not args.no_kit, args.mcp, args.mode)


def kit_for(args: argparse.Namespace) -> Path | None:
    return None if args.no_kit else KIT_DIR


def cmd_run(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    mcp = resolve_mcp(args.mcp, args.mcp_url)
    name = sandbox_name(args)
    kit = kit_for(args)

    if args.mode == "bash":
        return run_interactive(build_exec_argv(name), args.dry_run)

    if args.mode == "run":
        argv = build_sbx_argv("run", name, kit, mcp, workspace)
        rc = run_interactive(argv, args.dry_run)
        if not args.dry_run:
            print_cleanup_hint(args, name)
        return rc

    return cmd_attach(args, name, kit, mcp, workspace)


def print_cleanup_hint(args: argparse.Namespace, name: str) -> None:
    flags = []
    if args.mode != "run":
        flags += ["--mode", args.mode]
    if args.no_kit:
        flags.append("--no-kit")
    if args.mcp:
        flags += ["--mcp", args.mcp]
    print(
        f"\nSandbox '{name}' may still be running. To remove it:\n"
        f"  ./sbx_run.py stop --rm {' '.join(flags)}".rstrip()
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.dry_run:
        require_tool("sbx", "Run 'uv run sbx_setup.py' to install it.")
    if args.command == "stop":
        return cmd_stop(args)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
```

`cmd_attach` and `cmd_stop` are implemented in Task 3. To keep this task's tests green, add these temporary stubs now and replace them in Task 3:

```python
def cmd_attach(args, name, kit, mcp, workspace) -> int:
    raise NotImplementedError("implemented in Task 3")


def cmd_stop(args) -> int:
    raise NotImplementedError("implemented in Task 3")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: all tests PASS.

- [ ] **Step 5: Verify the script runs and is executable**

```bash
chmod +x sbx_run.py
python3 sbx_run.py --dry-run
python3 sbx_run.py --dry-run --mode bash --no-kit
python3 sbx_run.py --help
```

Expected: the first prints `sbx run --name claude-custom --kit /.../sbx-kits/claude-custom claude <cwd>`; the second prints `sbx exec -it claude bash`; the third prints usage without error.

- [ ] **Step 6: Commit**

```bash
git add sbx_run.py tests/test_sbx_run.py
git commit -m "feat: add CLI, process layer and run/bash modes to sbx_run"
```

---

### Task 3: `ssh` and `vscode` modes, idempotent create, and `stop`

The modes that need a created sandbox, an SSH alias, and the sandbox-side workspace path.

**Files:**
- Modify: `sbx_run.py`
- Modify: `tests/test_sbx_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1 and 2.
- Produces:
  - `parse_inspect_workspace(output: str) -> str | None`
  - `ensure_created(argv: list[str], dry_run: bool) -> None`
  - `ensure_mcp_registered(mcp: str, mcp_url: str | None, dry_run: bool) -> None`
  - `sandbox_workspace_path(name: str, host_workspace: Path, dry_run: bool) -> str`
  - `cmd_attach(...) -> int` (replaces the Task 2 stub)
  - `cmd_stop(args) -> int` (replaces the Task 2 stub)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sbx_run.py`, above the `if __name__` block:

```python
class TestParseInspectWorkspace(unittest.TestCase):
    """The exact `sbx inspect` output format is unverified (no sbx available
    at authoring time), so the parser is tolerant and returns None rather
    than guessing when it does not recognise the shape."""

    def test_json_workspace_key(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('{"workspace": "/work/proj"}'),
            "/work/proj",
        )

    def test_json_camel_case_key(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('{"workspaceDir": "/work/proj"}'),
            "/work/proj",
        )

    def test_json_nested_under_a_parent_object(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace(
                '{"config": {"WorkspaceDir": "/work/proj"}}'
            ),
            "/work/proj",
        )

    def test_json_list_wrapper(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('[{"workspace": "/work/proj"}]'),
            "/work/proj",
        )

    def test_unrecognised_output_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace("some unstructured text"))

    def test_invalid_json_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace("{not json"))

    def test_empty_output_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace(""))


class TestSandboxWorkspacePathDryRun(unittest.TestCase):
    def test_dry_run_uses_the_host_path_without_probing(self):
        result = sbx_run.sandbox_workspace_path(
            "claude-ssh", Path("/home/user/proj"), dry_run=True
        )
        self.assertEqual(result, "/home/user/proj")


class TestAttachDryRun(unittest.TestCase):
    def _run(self, argv):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(argv)
        return rc, buf.getvalue()

    def test_ssh_mode_creates_sets_up_ssh_then_connects(self):
        rc, out = self._run(["--dry-run", "--mode", "ssh", "--workspace", "/tmp/proj"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx create --name claude-custom-ssh", out)
        self.assertIn("sbx setup ssh --alias claude-custom-ssh.sbx", out)
        self.assertIn("ssh -t claude-custom-ssh.sbx", out)
        self.assertLess(out.index("sbx create"), out.index("sbx setup ssh"))
        self.assertLess(out.index("sbx setup ssh"), out.index("ssh -t"))

    def test_vscode_mode_emits_the_remote_flag(self):
        rc, out = self._run(["--dry-run", "--mode", "vscode", "--no-kit"])
        self.assertEqual(rc, 0)
        self.assertIn("--remote ssh-remote+claude-vscode.sbx", out)

    def test_mcp_registration_precedes_the_run(self):
        rc, out = self._run(["--dry-run", "--no-kit", "--mcp", "mslearn"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx mcp add mslearn --url https://learn.microsoft.com/api/mcp", out)
        self.assertLess(out.index("sbx mcp add"), out.index("sbx run"))


class TestStopDryRun(unittest.TestCase):
    def _run(self, argv):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(argv)
        return rc, buf.getvalue()

    def test_stop_without_rm(self):
        rc, out = self._run(["stop", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx stop claude-custom", out)
        self.assertNotIn("sbx rm", out)

    def test_stop_with_rm_stops_then_removes(self):
        rc, out = self._run(["stop", "--rm", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx stop claude-custom", out)
        self.assertIn("sbx rm claude-custom --force", out)
        self.assertLess(out.index("sbx stop"), out.index("sbx rm"))

    def test_stop_derives_the_same_name_as_the_matching_run(self):
        _, run_out = self._run(["--dry-run", "--mode", "ssh", "--no-kit"])
        _, stop_out = self._run(["stop", "--dry-run", "--mode", "ssh", "--no-kit"])
        self.assertIn("claude-ssh", run_out)
        self.assertIn("sbx stop claude-ssh", stop_out)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: FAIL with `AttributeError: module 'sbx_run' has no attribute 'parse_inspect_workspace'` and `NotImplementedError` from the Task 2 stubs.

- [ ] **Step 3: Write the implementation**

Add `import json` to the imports in `sbx_run.py`. Replace the two stubs from Task 2 with:

```python
_WORKSPACE_KEYS = ("workspace", "workspaceDir", "WorkspaceDir", "workspace_dir")


def parse_inspect_workspace(output: str) -> str | None:
    """Pull the sandbox-side workspace path out of `sbx inspect` output.

    The exact format is unverified -- sbx cannot be installed in the
    authoring environment -- so this recognises several plausible JSON
    shapes and returns None otherwise, letting the caller fall through to
    the next probe rather than acting on a guess.
    """
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return None

    def search(node) -> str | None:
        if isinstance(node, dict):
            for key in _WORKSPACE_KEYS:
                value = node.get(key)
                if isinstance(value, str) and value:
                    return value
            for value in node.values():
                found = search(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = search(item)
                if found:
                    return found
        return None

    return search(data)


def sandbox_workspace_path(name: str, host_workspace: Path, dry_run: bool) -> str:
    """Resolve the workspace path *inside* the sandbox.

    The host path is not usable directly on Windows, where the host form is
    C:\\Users\\... and the mount point is not. Probes in order of
    reliability: sbx inspect is host-side structured data and needs no
    running sandbox, whereas sbx exec requires one -- and --mode ssh reaches
    this immediately after sbx create, which may not have started it.
    """
    if dry_run:
        return str(host_workspace)

    rc, out = run_capture(["sbx", "inspect", name])
    if rc == 0:
        found = parse_inspect_workspace(out)
        if found:
            return found

    rc, out = run_capture(["sbx", "exec", name, "sh", "-c", "echo $WORKSPACE_DIR"])
    if rc == 0:
        candidate = out.strip().splitlines()[-1].strip() if out.strip() else ""
        if candidate.startswith("/"):
            return candidate

    return str(host_workspace)


def ensure_created(argv: list[str], dry_run: bool) -> None:
    """Create the sandbox, treating "already exists" as success."""
    if dry_run:
        print(render(argv))
        return
    rc, out = run_capture(argv)
    print(out, end="")
    if rc != 0 and "already exists" not in out:
        sys.exit(rc)


def ensure_mcp_registered(mcp: str, mcp_url: str | None, dry_run: bool) -> None:
    """Register an MCP server, skipping it if already present.

    `sbx mcp add` fails on an already-registered name, so a second
    `--mcp mslearn` would abort without this check.
    """
    add_argv = ["sbx", "mcp", "add", mcp, "--url", mcp_url_for(mcp, mcp_url)]
    if dry_run:
        print(render(add_argv))
        return
    rc, out = run_capture(["sbx", "mcp", "ls"])
    if rc == 0 and mcp in out.split():
        return
    run_interactive(add_argv)


def cmd_attach(
    args: argparse.Namespace,
    name: str,
    kit: Path | None,
    mcp: str | None,
    workspace: Path,
) -> int:
    """Handle --mode ssh and --mode vscode."""
    code_exe = None
    if args.mode == "vscode" and not args.dry_run:
        code_exe = require_tool(
            "code",
            "Install VS Code and the 'Remote - SSH' extension.",
        )

    ensure_created(build_sbx_argv("create", name, kit, mcp, workspace), args.dry_run)

    rc = run_interactive(
        ["sbx", "setup", "ssh", "--alias", alias_for(name)], args.dry_run
    )
    if rc != 0:
        return rc

    sandbox_path = sandbox_workspace_path(name, workspace, args.dry_run)

    if args.mode == "vscode":
        argv = build_vscode_argv(code_exe or "code", name, sandbox_path)
    else:
        argv = build_ssh_argv(name, sandbox_path)

    rc = run_interactive(argv, args.dry_run)
    if not args.dry_run:
        print_cleanup_hint(args, name)
    return rc


def cmd_stop(args: argparse.Namespace) -> int:
    name = sandbox_name(args)
    rc = run_interactive(["sbx", "stop", name], args.dry_run)
    if args.rm:
        rc = run_interactive(["sbx", "rm", name, "--force"], args.dry_run)
    return rc
```

In `cmd_run`, register the MCP server before the run. Replace the `if args.mode == "run":` branch with:

```python
    if mcp:
        ensure_mcp_registered(mcp, args.mcp_url, args.dry_run)

    if args.mode == "run":
        argv = build_sbx_argv("run", name, kit, mcp, workspace)
        rc = run_interactive(argv, args.dry_run)
        if not args.dry_run:
            print_cleanup_hint(args, name)
        return rc
```

Place the `if mcp:` block after the `--mode bash` early return, so `--mode bash` never registers an MCP server.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: all tests PASS.

- [ ] **Step 5: Verify every mode renders**

```bash
for m in run bash ssh vscode; do
  echo "--- $m"; python3 sbx_run.py --dry-run --mode "$m"
done
python3 sbx_run.py --dry-run --no-kit --mcp mslearn
python3 sbx_run.py stop --rm --dry-run
```

Expected: each prints its command sequence with no traceback.

- [ ] **Step 6: Commit**

```bash
git add sbx_run.py tests/test_sbx_run.py
git commit -m "feat: add ssh and vscode modes, idempotent create and stop

sbx mcp add fails on an already-registered name, so registration checks
sbx mcp ls first. The sandbox-side workspace path is probed via sbx
inspect before sbx exec, since exec needs a running sandbox."
```

---

### Task 4: `sbx_setup.py`

Host bootstrap, gated on platform, with the GitHub secret.

**Files:**
- Create: `sbx_setup.py`
- Test: `tests/test_sbx_setup.py`

**Interfaces:**
- Consumes: nothing (self-contained by design; the ~20 duplicated lines are deliberate, see the spec's File layout section).
- Produces:
  - `Cmd` NamedTuple with fields `args: list[str] | str`, `shell: bool = False`, `tolerate_failure: bool = False`
  - `current_platform() -> str`
  - `build_setup_commands(platform: str, user: str) -> list[Cmd]`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sbx_setup.py`:

```python
"""Unit tests for sbx_setup.py command building."""

import contextlib
import io
import unittest

import sbx_setup


class TestCurrentPlatform(unittest.TestCase):
    def test_maps_sys_platform_names(self):
        self.assertEqual(sbx_setup.normalise_platform("linux"), "linux")
        self.assertEqual(sbx_setup.normalise_platform("win32"), "windows")
        self.assertEqual(sbx_setup.normalise_platform("darwin"), "darwin")

    def test_unknown_platform_exits_rather_than_guessing(self):
        with self.assertRaises(SystemExit):
            sbx_setup.normalise_platform("plan9")


class TestBuildSetupCommands(unittest.TestCase):
    def _rendered(self, platform, user="agent"):
        return [
            c.args if isinstance(c.args, str) else " ".join(c.args)
            for c in sbx_setup.build_setup_commands(platform, user)
        ]

    def test_linux_sequence(self):
        self.assertEqual(
            self._rendered("linux"),
            [
                "curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh",
                "sudo apt-get install -y docker-sbx",
                "sudo usermod -aG kvm agent",
                "sbx login",
            ],
        )

    def test_linux_pipeline_is_the_only_shell_command(self):
        cmds = sbx_setup.build_setup_commands("linux", "agent")
        self.assertTrue(cmds[0].shell)
        for cmd in cmds[1:]:
            self.assertFalse(cmd.shell)

    def test_linux_uses_the_given_user_not_a_literal(self):
        self.assertIn("sudo usermod -aG kvm someone-else", self._rendered("linux", "someone-else"))

    def test_windows_sequence(self):
        rendered = self._rendered("windows")
        self.assertIn("winget install -h Docker.sbx", rendered)
        self.assertIn("sbx login", rendered)
        self.assertTrue(
            any("HypervisorPlatform" in r for r in rendered),
            "the hypervisor check must be present",
        )

    def test_windows_hypervisor_check_tolerates_failure(self):
        """Get-WindowsOptionalFeature needs elevation; a failure there must
        not abort the install."""
        cmds = sbx_setup.build_setup_commands("windows", "agent")
        check = next(
            c for c in cmds if "HypervisorPlatform" in " ".join(c.args)
        )
        self.assertTrue(check.tolerate_failure)

    def test_darwin_sequence(self):
        self.assertEqual(
            self._rendered("darwin"),
            [
                "brew trust docker/tap",
                "brew install docker/tap/sbx",
                "sbx login",
            ],
        )

    def test_no_command_uses_shell_except_the_linux_pipeline(self):
        for platform in ("windows", "darwin"):
            for cmd in sbx_setup.build_setup_commands(platform, "agent"):
                self.assertFalse(cmd.shell, f"{platform}: {cmd.args}")


class TestDryRun(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_setup.main(argv)
        return rc, buf.getvalue()

    def test_dry_run_linux_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "linux"])
        self.assertEqual(rc, 0)
        self.assertIn("REPO_ONLY=1", out)

    def test_dry_run_windows_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "windows"])
        self.assertEqual(rc, 0)
        self.assertIn("winget install -h Docker.sbx", out)

    def test_dry_run_darwin_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "darwin"])
        self.assertEqual(rc, 0)
        self.assertIn("brew install docker/tap/sbx", out)

    def test_dry_run_mentions_the_kvm_group_relogin(self):
        """newgrp kvm cannot work from a subprocess -- it spawns a
        replacement shell that exits immediately -- so the instruction is
        printed instead of faked."""
        _, out = self._run(["--dry-run", "--platform", "linux"])
        self.assertIn("log out", out.lower())

    def test_secret_gh_dry_run(self):
        rc, out = self._run(["--dry-run", "--secret-gh"])
        self.assertEqual(rc, 0)
        self.assertIn("gh auth token", out)
        self.assertIn("sbx secret set github --force", out)

    def test_secret_gh_skips_the_install(self):
        _, out = self._run(["--dry-run", "--secret-gh"])
        self.assertNotIn("docker-sbx", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: `ModuleNotFoundError: No module named 'sbx_setup'`.

- [ ] **Step 3: Write the implementation**

Create `sbx_setup.py`:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""One-time host bootstrap for Docker Sandboxes.

Installs the sbx CLI for the current platform and optionally stores a
GitHub token as an sbx secret. Day-to-day sandbox launching lives in
sbx_run.py.
"""

import argparse
import getpass
import shlex
import subprocess
import sys
from typing import NamedTuple


class Cmd(NamedTuple):
    args: list[str] | str
    shell: bool = False
    tolerate_failure: bool = False


PLATFORM_MAP = {
    "linux": "linux",
    "win32": "windows",
    "darwin": "darwin",
}

RELOGIN_NOTE = (
    "\nThe kvm group membership only takes effect in new login sessions.\n"
    "Log out and log back in (or reboot) before running sbx.\n"
    "This step cannot be automated: `newgrp kvm` spawns a replacement shell\n"
    "that exits immediately, leaving this process's groups unchanged.\n"
)


def normalise_platform(raw: str) -> str:
    """Map a sys.platform value or an explicit --platform to a known name."""
    if raw in PLATFORM_MAP.values():
        return raw
    try:
        return PLATFORM_MAP[raw]
    except KeyError:
        sys.exit(
            f"error: unsupported platform '{raw}'. "
            "Docker Sandboxes supports Ubuntu 24.04+, macOS 14+ and Windows 11."
        )


def current_platform() -> str:
    return normalise_platform(sys.platform)


def build_setup_commands(platform: str, user: str) -> list[Cmd]:
    """The install sequence for one platform. Pure -- no I/O."""
    if platform == "linux":
        return [
            # The one shell pipeline in this project: a fixed literal with
            # no interpolated input.
            Cmd("curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh", shell=True),
            Cmd(["sudo", "apt-get", "install", "-y", "docker-sbx"]),
            Cmd(["sudo", "usermod", "-aG", "kvm", user]),
            Cmd(["sbx", "login"]),
        ]
    if platform == "windows":
        return [
            Cmd(
                [
                    "powershell", "-NoProfile", "-Command",
                    "(Get-WindowsOptionalFeature -Online "
                    "-FeatureName HypervisorPlatform).State",
                ],
                tolerate_failure=True,
            ),
            Cmd(["winget", "install", "-h", "Docker.sbx"]),
            Cmd(["sbx", "login"]),
        ]
    return [
        Cmd(["brew", "trust", "docker/tap"]),
        Cmd(["brew", "install", "docker/tap/sbx"]),
        Cmd(["sbx", "login"]),
    ]


def render(cmd: Cmd) -> str:
    if isinstance(cmd.args, str):
        return cmd.args
    return " ".join(shlex.quote(a) for a in cmd.args)


def run_interactive(cmd: Cmd, dry_run: bool) -> int:
    """Run with stdio inherited.

    Required, not optional: sudo prompts for a password, sbx login is
    interactive, and winget writes progress to the console. Capturing any
    of them hangs on an invisible prompt.
    """
    if dry_run:
        print(render(cmd))
        return 0
    if cmd.shell:
        return subprocess.run(cmd.args, shell=True).returncode
    return subprocess.run(cmd.args).returncode


def do_install(platform: str, dry_run: bool) -> int:
    for cmd in build_setup_commands(platform, getpass.getuser()):
        rc = run_interactive(cmd, dry_run)
        if rc != 0 and not cmd.tolerate_failure:
            return rc
    if platform == "linux":
        print(RELOGIN_NOTE)
    return 0


def do_secret_gh(dry_run: bool) -> int:
    """Store a GitHub token as an sbx secret.

    The only place this script captures output: `gh auth token` is
    non-interactive, and the token is piped to sbx via stdin rather than
    appearing in an argument list or the process table.
    """
    if dry_run:
        print("gh auth token")
        print("sbx secret set github --force  # token supplied on stdin")
        print("sbx secret ls")
        return 0

    proc = subprocess.run(
        ["gh", "auth", "token"], stdout=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        print("error: 'gh auth token' failed. Run 'gh auth login' first.", file=sys.stderr)
        return proc.returncode

    rc = subprocess.run(
        ["sbx", "secret", "set", "github", "--force"],
        input=proc.stdout,
        text=True,
    ).returncode
    if rc != 0:
        return rc
    return subprocess.run(["sbx", "secret", "ls"]).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sbx_setup.py",
        description="Install the sbx CLI and configure host secrets.",
    )
    parser.add_argument(
        "--secret-gh",
        action="store_true",
        help="store a GitHub token as an sbx secret instead of installing",
    )
    parser.add_argument(
        "--platform",
        choices=["linux", "windows", "darwin"],
        help="override platform detection (for testing)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print commands instead of running them"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.secret_gh:
        return do_secret_gh(args.dry_run)
    platform = normalise_platform(args.platform) if args.platform else current_platform()
    return do_install(platform, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest discover -s tests -t . -v
```

Expected: all tests PASS.

- [ ] **Step 5: Verify all three platforms render from this host**

```bash
chmod +x sbx_setup.py
for p in linux windows darwin; do
  echo "--- $p"; python3 sbx_setup.py --dry-run --platform "$p"
done
python3 sbx_setup.py --dry-run --secret-gh
```

Expected: each prints its sequence; the Linux one ends with the log-out note.

- [ ] **Step 6: Commit**

```bash
git add sbx_setup.py tests/test_sbx_setup.py
git commit -m "feat: add platform-gated sbx_setup.py with GitHub secret support"
```

---

### Task 5: Move the bash scripts into `scripts/` and fix their paths

Frozen at current feature parity: moved, path-fixed, and the `30`/`31` defect corrected. No restructuring.

**Files:**
- Move: all ten `*.sh` from the repository root to `scripts/`
- Modify: `scripts/20_docker_sbx_claude_nokit.sh`, `21_`, `22_`, `23_`, `30_`, `31_`, `32_`, `33_`

`00_docker_sbx_setup.sh` and `10_docker_sbx_secret_gh.sh` reference neither `$(pwd)` nor the kit, so they move unchanged.

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing consumed by later tasks. Task 6 documents these files.

- [ ] **Step 1: Move the files with history preserved**

```bash
mkdir -p scripts
git mv 00_docker_sbx_setup.sh 10_docker_sbx_secret_gh.sh \
       20_docker_sbx_claude_nokit.sh 21_docker_sbx_claude_mcp.sh \
       22_docker_sbx_claude_ssh.sh 23_docker_sbx_claude_ssh_vscode.sh \
       30_docker_sbx_claude_custom_kit.sh 31_docker_sbx_claude_custom_kit_bash.sh \
       32_docker_sbx_claude_custom_kit_ssh.sh 33_docker_sbx_claude_custom_kit_ssh_vscode.sh \
       scripts/
git status --short
```

Expected: ten `R` (rename) entries.

- [ ] **Step 2: Add `REPO_ROOT` to the eight scripts that need it**

For each of `20_`, `21_`, `22_`, `23_`, `30_`, `31_`, `32_`, `33_`, insert this line immediately after `set -euxo pipefail`:

```bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```

Deriving from `${BASH_SOURCE[0]}` rather than a literal `$(pwd)/..` makes this independent of the invocation directory. A literal `$(pwd)/..` would be correct only after `cd scripts/`, and would mount the repository's *parent* when run from the root.

Apply with:

```bash
cd scripts
for f in 20_* 21_* 22_* 23_* 30_* 31_* 32_* 33_*; do
  sed -i '/^set -euxo pipefail$/a\
\
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." \&\& pwd)"' "$f"
done
cd ..
head -6 scripts/30_docker_sbx_claude_custom_kit.sh
```

Expected: the `REPO_ROOT` line appears after `set -euxo pipefail`.

- [ ] **Step 3: Repoint the workspace and kit paths**

```bash
cd scripts
sed -i 's|"\$(pwd)"|"$REPO_ROOT"|g; s|cd \$(pwd) |cd $REPO_ROOT |g' 2*.sh 3*.sh
sed -i 's|--kit \./sbx-kits/claude-custom/|--kit "$REPO_ROOT/sbx-kits/claude-custom/"|g' 3*.sh
cd ..
grep -n 'REPO_ROOT\|pwd' scripts/*.sh
```

Expected: no remaining `$(pwd)` outside the `REPO_ROOT` definition itself; every `--kit` is `"$REPO_ROOT/sbx-kits/claude-custom/"`.

- [ ] **Step 4: Fix the `30`/`31` sandbox name mismatch**

`31_docker_sbx_claude_custom_kit_bash.sh` execs into `claude-custom`, but `30_docker_sbx_claude_custom_kit.sh` creates `claude-custom-kit`. Correct the exec target:

```bash
sed -i 's|sbx exec -it claude-custom bash|sbx exec -it claude-custom-kit bash|' \
  scripts/31_docker_sbx_claude_custom_kit_bash.sh
grep -n 'sbx exec' scripts/31_docker_sbx_claude_custom_kit_bash.sh
```

Expected: `sbx exec -it claude-custom-kit bash`.

The bash scripts keep their existing sandbox names (`claude-custom-kit`, `claude-nokit`, and so on) rather than adopting the Python-derived ones. Renaming them would break anyone's running sandboxes for no gain, since the two interfaces are not meant to share sandboxes.

- [ ] **Step 5: Verify every script still parses and resolves paths correctly**

```bash
for f in scripts/*.sh; do bash -n "$f" || echo "SYNTAX ERROR: $f"; done
echo "--- resolution check (run from repo root and from scripts/)"
bash -c 'BASH_SOURCE=(scripts/30_docker_sbx_claude_custom_kit.sh); \
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; echo "$REPO_ROOT"'
(cd scripts && bash -c 'BASH_SOURCE=(30_docker_sbx_claude_custom_kit.sh); \
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; echo "$REPO_ROOT"')
```

Expected: no syntax errors, and both `REPO_ROOT` echoes print the same absolute repository root path.

- [ ] **Step 6: Commit**

```bash
git add -A scripts/
git commit -m "refactor: move bash scripts to scripts/ and anchor paths to repo root

Derive REPO_ROOT from BASH_SOURCE so the scripts work from any invocation
directory, and fix 31 to exec into claude-custom-kit, the sandbox 30
actually creates."
```

---

### Task 6: Documentation

Root `README.md` describes only the Python scripts; a new `scripts/README.md` describes the bash ones.

**Files:**
- Modify: `README.md`
- Create: `scripts/README.md`

**Interfaces:**
- Consumes: the CLI surface of `sbx_run.py` (Tasks 1–3) and `sbx_setup.py` (Task 4), and the moved scripts (Task 5).
- Produces: nothing.

- [ ] **Step 1: Replace the "Helper scripts" and "Quick start" sections in `README.md`**

Delete the existing `## Helper scripts` section (the ten-row table and its intro paragraph) and the `## Quick start` section. Replace both with:

````markdown
## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — supplies the Python interpreter for the
  scripts below. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
  on Linux and macOS, or `winget install astral-sh.uv` on Windows.
- `sbx` itself is installed by `sbx_setup.py`.

## `sbx_setup.py` — one-time host setup

Installs the `sbx` CLI for the current platform and signs in.

| Flag | Effect |
| ---- | ------ |
| `--secret-gh` | Store a GitHub token (`gh auth token`) as an `sbx` secret. |
| `--platform linux\|windows\|darwin` | Override platform detection. |
| `--dry-run` | Print the commands instead of running them. |

On Linux the `kvm` group membership only takes effect in a new login session,
so log out and back in after the install. This step cannot be automated:
`newgrp kvm` spawns a replacement shell that exits immediately.

## `sbx_run.py` — launch a sandbox

Runs Claude Code in a sandbox with the current directory mounted. The sandbox
name is derived from the kit, MCP and mode you select, so the same command
always reaches the same sandbox.

| Flag | Effect |
| ---- | ------ |
| `--mode run` | Run Claude Code in the sandbox (default). |
| `--mode bash` | Open a bash shell in the sandbox `--mode run` created. |
| `--mode ssh` | Create the sandbox, register an SSH alias, and connect. |
| `--mode vscode` | Same, then open VS Code over Remote-SSH. |
| `--no-kit` | Use the plain `claude` agent instead of the `claude-custom` kit. |
| `--mcp mslearn` | Attach the Microsoft Learn MCP server. |
| `--mcp NAME --mcp-url URL` | Attach any other MCP server. |
| `--workspace PATH` | Mount some other directory (default: the current one). |
| `--name NAME` | Override the derived sandbox name. |
| `--dry-run` | Print the commands instead of running them. |

`sbx_run.py stop [--rm]` stops the sandbox the same flags would launch, and
with `--rm` removes it. Sandboxes are not cleaned up automatically; the script
prints the exact `stop` command when a session ends.

`--mode vscode` requires the "Remote - SSH" extension in VS Code.

## Invocation

On Linux and macOS the PEP 723 shebang makes the scripts directly executable:

```console
$ ./sbx_run.py --mode ssh
```

Windows has no shebang mechanism, so invoke `uv` explicitly:

```console
> uv run sbx_run.py --mode ssh
```

## Quick start

```console
$ uv run sbx_setup.py          # one-time host setup
$ ./sbx_run.py                 # Claude Code with the custom kit
```

## Bash scripts

The original bash helper scripts remain in [`scripts/`](scripts/README.md) as a
fallback for hosts without `uv`. They are frozen at their current feature set.
````

Leave `## What is a Docker Sandbox?`, `### The claude-custom kit`, `## Known issues` and `## References` unchanged.

- [ ] **Step 2: Create `scripts/README.md`**

```markdown
# Bash helper scripts

The original bash scripts for Docker Sandboxes, kept as a fallback for hosts
without [`uv`](https://docs.astral.sh/uv/). They are **frozen at their current
feature set**: paths are maintained so they keep working, but new modes and
flags go to the Python scripts described in [`../README.md`](../README.md),
which is the maintained interface.

Each script derives `REPO_ROOT` from its own location, so it can be run from
anywhere:

```console
$ ./scripts/30_docker_sbx_claude_custom_kit.sh
$ cd scripts && ./30_docker_sbx_claude_custom_kit.sh   # equivalent
```

Unlike `sbx_run.py`, which mounts the current directory, these scripts always
mount the repository root.

| Script | Purpose |
| ------ | ------- |
| `00_docker_sbx_setup.sh` | Install `docker-sbx`, configure KVM access, and `sbx login`. |
| `10_docker_sbx_secret_gh.sh` | Store a GitHub token as an `sbx` secret. |
| `20_docker_sbx_claude_nokit.sh` | Run Claude Code with no custom kit. |
| `21_docker_sbx_claude_mcp.sh` | Run Claude Code with the Microsoft Learn MCP server. |
| `22_docker_sbx_claude_ssh.sh` | Create a sandbox and SSH into it. |
| `23_docker_sbx_claude_ssh_vscode.sh` | Open a sandbox in VS Code over Remote-SSH. |
| `30_docker_sbx_claude_custom_kit.sh` | Run Claude Code with the `claude-custom` kit. |
| `31_docker_sbx_claude_custom_kit_bash.sh` | Open a bash shell in the custom-kit sandbox. |
| `32_docker_sbx_claude_custom_kit_ssh.sh` | Create a custom-kit sandbox and SSH into it. |
| `33_docker_sbx_claude_custom_kit_ssh_vscode.sh` | Open a custom-kit sandbox in VS Code over Remote-SSH. |

## Cleanup

None of these scripts remove their sandbox. A sandbox left running keeps
consuming resources, so stop and remove it when you are finished:

```console
$ sbx stop <name>
$ sbx rm <name> --force
```

Sandbox names are `claude-nokit`, `claude-mcp`, `claude-ssh`,
`claude-ssh-vscode`, `claude-custom-kit`, `claude-custom-ssh` and
`claude-custom-ssh-vscode`. List what is running with `sbx ls`.

## Python equivalents

| Bash script | Python equivalent |
| ----------- | ----------------- |
| `00_docker_sbx_setup.sh` | `uv run sbx_setup.py` |
| `10_docker_sbx_secret_gh.sh` | `uv run sbx_setup.py --secret-gh` |
| `20_docker_sbx_claude_nokit.sh` | `./sbx_run.py --no-kit` |
| `21_docker_sbx_claude_mcp.sh` | `./sbx_run.py --no-kit --mcp mslearn` |
| `22_docker_sbx_claude_ssh.sh` | `./sbx_run.py --no-kit --mode ssh` |
| `23_docker_sbx_claude_ssh_vscode.sh` | `./sbx_run.py --no-kit --mode vscode` |
| `30_docker_sbx_claude_custom_kit.sh` | `./sbx_run.py` |
| `31_docker_sbx_claude_custom_kit_bash.sh` | `./sbx_run.py --mode bash` |
| `32_docker_sbx_claude_custom_kit_ssh.sh` | `./sbx_run.py --mode ssh` |
| `33_docker_sbx_claude_custom_kit_ssh_vscode.sh` | `./sbx_run.py --mode vscode` |

The two interfaces use different sandbox names, so they can be run side by
side without interfering. Switching to the Python scripts leaves the old
sandboxes running — remove them once with `sbx ls` and `sbx rm`.
```

- [ ] **Step 3: Verify no stale paths remain in the documentation**

```bash
grep -n '^\$ \./[0-9]\|(\./[0-9]' README.md || echo "OK: no root-level script paths in README"
grep -rn 'Baramundi\|BARAMUNDI' README.md scripts/README.md || echo "OK: company name lowercase"
ls scripts/README.md README.md
```

Expected: both `OK:` lines print, and both files exist.

- [ ] **Step 4: Verify the documented commands actually work**

```bash
python3 -m unittest discover -s tests -t . -v
python3 sbx_setup.py --dry-run --platform linux
python3 sbx_run.py --dry-run
python3 sbx_run.py --dry-run --mode vscode --no-kit
python3 sbx_run.py stop --rm --dry-run
for f in scripts/*.sh; do bash -n "$f" || echo "SYNTAX ERROR: $f"; done
```

Expected: all tests pass, every command prints its sequence, no syntax errors.

- [ ] **Step 5: Commit**

```bash
git add README.md scripts/README.md
git commit -m "docs: describe the python scripts in README and bash scripts in scripts/"
```

---

## Plan verification

Every Python block in this plan was assembled into working files and executed
before the plan was committed: **66 tests, all passing**. The `sed` commands in
Task 5 were run against copies of the ten real scripts — syntax clean, no
`$(pwd)` left outside the `REPO_ROOT` definition, all three `--kit` references
repointed, and `31` corrected to `claude-custom-kit`.

The missing `tests/__init__.py` was found this way: without it, discovery
aborts before running a single test.

## Verification checklist

Run from the repository root after Task 6:

```bash
python3 -m unittest discover -s tests -t . -v
python3 sbx_run.py --dry-run
python3 sbx_setup.py --dry-run --platform windows
for f in scripts/*.sh; do bash -n "$f"; done
git log --oneline -6
```

## Deferred to first real run

These cannot be verified without a working `sbx` install, which is not
available in the authoring environment:

1. **`parse_inspect_workspace` against real `sbx inspect` output.** The parser
   recognises several plausible JSON shapes and returns `None` otherwise,
   falling through to the `sbx exec` probe and then the host path. If neither
   probe fires, `--mode ssh` still works on Linux (host and sandbox paths
   coincide) but may `cd` to the wrong directory on Windows. Check which branch
   fires and simplify the chain accordingly.
2. **TTY inheritance** for `sbx run`, `ssh -t`, `sbx exec -it` and
   `code --remote`. A hang here means something is capturing that should not.
3. **Argument order for `sbx run`.** Script `21` writes
   `sbx run claude --name ...` while `20` and `30` write
   `sbx run --name ... claude`. The implementation follows the majority — flags
   first, agent then workspace last. Confirm `sbx` accepts it.
4. **`sbx mcp ls` output format.** `ensure_mcp_registered` checks membership
   with `mcp in out.split()`. If the listing is tabular with the name embedded
   in a wider column, this still works; if it is JSON, tighten the check.
5. **The Windows hypervisor check.** `Get-WindowsOptionalFeature` requires
   elevation, so it is marked `tolerate_failure`. Confirm it produces something
   useful when run elevated.
