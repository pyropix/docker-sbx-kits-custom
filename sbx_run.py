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
