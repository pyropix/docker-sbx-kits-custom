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
import shlex
import shutil
import subprocess
import sys
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


def cmd_attach(args, name, kit, mcp, workspace) -> int:
    raise NotImplementedError("implemented in Task 3")


def cmd_stop(args) -> int:
    raise NotImplementedError("implemented in Task 3")


if __name__ == "__main__":
    sys.exit(main())
