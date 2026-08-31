#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Launch Claude Code in a Docker Sandbox.

The sandbox name is derived from (kit, mcp, mode) rather than typed per
scenario, so the ten bash scripts this replaces cannot drift apart again.
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Opt out of all sbx analytics for every command this script runs, mirroring
# scripts/00_docker_sbx_setup.sh. Child processes inherit os.environ.
os.environ["SBX_NO_TELEMETRY"] = "1"

# Mode -> sandbox-name suffix.
#
# `agent`, `bash`, and `tmux` deliberately share one empty suffix: they are
# three different ways to attach to the same persistent sandbox (create it if
# missing, then run the agent, or exec bash/tmux into it). `ssh` and `vscode`
# get their own names because those sandboxes are set up for SSH access.
MODE_SUFFIX = {
    "agent": "",
    "bash": "",
    "tmux": "",
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
    return "claude" + ("-custom" if use_kit else "") + ("-mcp" if mcp else "") + MODE_SUFFIX[mode]


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


def build_exec_argv(name: str, command: list[str]) -> list[str]:
    return ["sbx", "exec", "-it", name, *command]


def build_attach_argv(mode: str, name: str) -> list[str]:
    """Attach command for --mode agent/bash/tmux once the sandbox exists."""
    if mode == "agent":
        return build_reattach_argv(name)
    if mode == "bash":
        return build_exec_argv(name, ["bash"])
    # tmux: attach to session "main" if it exists, create it otherwise, so
    # repeated `--mode tmux` invocations return to the same session.
    return build_exec_argv(name, ["tmux", "new-session", "-A", "-s", "main"])


def build_reattach_argv(name: str) -> list[str]:
    """Re-attach to an existing sandbox without re-specifying kit/workspace/MCP.

    `sbx run --name NAME` re-attaches when the sandbox already exists, reading
    the agent from its spec. Passing --kit or --static-mcp on re-attach errors.
    """
    return ["sbx", "run", "--name", name]


def sandbox_exists(name: str) -> bool:
    rc, _ = run_capture(["sbx", "inspect", name, "--json"])
    return rc == 0


def build_ssh_argv(name: str, sandbox_path: str) -> list[str]:
    return ["ssh", "-t", alias_for(name), f"cd {shlex.quote(sandbox_path)} ; bash --login"]


def build_vscode_argv(code_exe: str, name: str, sandbox_path: str) -> list[str]:
    return [code_exe, "--remote", f"ssh-remote+{alias_for(name)}", sandbox_path]


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


def normalise_exit(rc: int) -> int:
    """Map a child return code to a POSIX shell exit status.

    subprocess returns -N for a child killed by signal N; a bare
    sys.exit(-N) wraps to 256-N (e.g. -15 -> 241). Shells report a
    signalled child as 128+N (143 for SIGTERM), so mirror that.
    """
    return 128 + (-rc) if rc < 0 else rc


def invocation_prefix() -> str:
    """How to re-invoke this script on the current platform.

    The shebang runs it directly on POSIX; on Windows the docs call it via
    `uv run` because the shebang does not apply there.
    """
    return "uv run sbx_run.py" if sys.platform == "win32" else "./sbx_run.py"


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
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
        "command",
        nargs="?",
        choices=["run", "stop"],
        default="run",
        metavar="{run,stop}",
        help="action to perform (default: run)",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(MODE_SUFFIX),
        default="agent",
        help="how to attach to the sandbox (default: agent)",
    )
    parser.add_argument("--no-kit", action="store_true", help="use the plain claude agent")
    parser.add_argument("--mcp", help="MCP server to attach")
    parser.add_argument("--mcp-url", help="URL for an MCP server not in KNOWN_MCP")
    parser.add_argument("--name", help="override the derived sandbox name")
    parser.add_argument("--workspace", help="directory to mount (default: current directory)")
    parser.add_argument("--rm", action="store_true", help="with stop: also remove the sandbox")
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

    if args.mode in ("agent", "bash", "tmux"):
        return cmd_local(args, name, kit, mcp, workspace)

    return cmd_attach(args, name, kit, mcp, workspace)


def cmd_local(
    args: argparse.Namespace,
    name: str,
    kit: Path | None,
    mcp: str | None,
    workspace: Path,
) -> int:
    """Handle --mode agent/bash/tmux: create the sandbox if needed, then attach.

    Skips `sbx create` entirely when the sandbox already exists, so kit,
    workspace, and MCP keep coming from whatever created it originally.
    """
    if mcp:
        ensure_mcp_registered(mcp, args.mcp_url, args.dry_run)

    if args.dry_run or not sandbox_exists(name):
        ensure_created(build_sbx_argv("create", name, kit, mcp, workspace), args.dry_run)

    rc = run_interactive(build_attach_argv(args.mode, name), args.dry_run)
    if not args.dry_run:
        prompt_cleanup(args, name)
    return rc


def prompt_cleanup(args: argparse.Namespace, name: str) -> None:
    flags = []
    if args.name:
        # --name alone determines the sandbox; the other flags would be
        # redundant (and could even mismatch it), so it wins outright.
        flags += ["--name", args.name]
    else:
        if args.mode != "agent":
            flags += ["--mode", args.mode]
        if args.no_kit:
            flags.append("--no-kit")
        if args.mcp:
            flags += ["--mcp", args.mcp]

    stop_hint = (
        f"\nSandbox '{name}' may still be running. To remove it:\n"
        f"  {invocation_prefix()} stop --rm {' '.join(flags)}".rstrip()
    )

    try:
        answer = input(f"\nStop and remove sandbox '{name}'? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer.startswith("y"):
        run_interactive(["sbx", "stop", name])
        run_interactive(["sbx", "rm", name, "--force"])
    else:
        print(stop_hint)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mcp_url and not args.mcp:
        parser.error("--mcp-url requires --mcp NAME")
    if args.rm and args.command != "stop":
        parser.error("--rm is only valid with the 'stop' command")
    if not args.dry_run:
        require_tool("sbx", "Run 'uv run sbx_setup.py' to install it.")
    if args.command == "stop":
        return cmd_stop(args)
    return cmd_run(args)


_WORKSPACE_KEYS = ("workspace", "workspaceDir", "WorkspaceDir", "workspace_dir")


def parse_inspect_workspace(output: str) -> str | None:
    """Pull the host-side workspace path out of `sbx inspect --json` output.

    Verified against sbx daemon v0.39.0: the workspace lives at the top-level
    "workspace" key, and it is the host path (identical to the sandbox path
    only because Linux-style hosts bind-mount at the same location -- the
    caller's leading-"/" guard is what rejects this value on Windows hosts,
    where it differs). Additional key variants are accepted for forwards
    compatibility. Returns None for unrecognised shapes, letting the caller
    fall through to the next probe.
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

    rc, out = run_capture(["sbx", "inspect", name, "--json"])
    if rc == 0:
        found = parse_inspect_workspace(out)
        # Same sanity check as the exec probe below: `sbx inspect` is
        # host-side data, so a non-absolute candidate is most plausibly the
        # *host* path (e.g. a Windows path), not the sandbox-side one this
        # probe exists to find. Fall through rather than guess.
        if found and found.startswith("/"):
            return found

    rc, out = run_capture(["sbx", "exec", name, "sh", "-c", "echo $WORKSPACE_DIR"])
    if rc == 0:
        candidate = out.strip().splitlines()[-1].strip() if out.strip() else ""
        if candidate.startswith("/"):
            return candidate

    return str(host_workspace)


def ensure_created(argv: list[str], dry_run: bool) -> None:
    """Create the sandbox with the real terminal attached.

    Callers must gate this on `not sandbox_exists(name)` first: `sbx create`
    is run interactively (stdio inherited) so its progress renders live
    instead of being buffered and dumped after the fact, which means there's
    no captured text left to string-match an "already exists" error against.
    """
    rc = run_interactive(argv, dry_run)
    if not dry_run and rc != 0:
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
    # `sbx mcp inspect NAME` exits 0 iff NAME is registered -- an exact
    # per-server check, unlike a token match over the whole `sbx mcp ls`
    # listing, which a short or generic name could false-positive.
    rc, _ = run_capture(["sbx", "mcp", "inspect", mcp])
    if rc == 0:
        if mcp_url:
            print(
                f"warning: MCP server '{mcp}' is already registered; "
                f"--mcp-url is ignored. Use 'sbx mcp rm {mcp}' first to re-register."
            )
        return
    rc = run_interactive(add_argv)
    if rc != 0:
        # A failed registration would otherwise surface later as an obscure
        # `sbx run --static-mcp` failure.
        sys.exit(normalise_exit(rc))


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

    if args.dry_run or not sandbox_exists(name):
        ensure_created(build_sbx_argv("create", name, kit, mcp, workspace), args.dry_run)

    rc = run_interactive(["sbx", "setup", "ssh", "--alias", alias_for(name)], args.dry_run)
    if rc != 0:
        return rc

    sandbox_path = sandbox_workspace_path(name, workspace, args.dry_run)

    if args.mode == "vscode":
        # code_exe is None only in --dry-run (require_tool was skipped); the
        # literal "code" is printed but never executed.
        argv = build_vscode_argv(code_exe or "code", name, sandbox_path)
    else:
        argv = build_ssh_argv(name, sandbox_path)

    rc = run_interactive(argv, args.dry_run)
    if not args.dry_run:
        prompt_cleanup(args, name)
    return rc


def cmd_stop(args: argparse.Namespace) -> int:
    name = sandbox_name(args)
    rc = run_interactive(["sbx", "stop", name], args.dry_run)
    if args.rm:
        # Always attempt the removal, but keep a failed `sbx stop` visible:
        # don't let a successful rm mask it.
        rm_rc = run_interactive(["sbx", "rm", name, "--force"], args.dry_run)
        rc = rc or rm_rc
    return rc


if __name__ == "__main__":
    try:
        sys.exit(normalise_exit(main()))
    except KeyboardInterrupt:
        # Ctrl-C out of a sandbox TUI should exit quietly, not traceback.
        sys.exit(130)
