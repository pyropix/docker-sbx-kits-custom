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
import shutil
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


def normalise_exit(rc: int) -> int:
    """Map a child return code to a POSIX shell exit status.

    subprocess returns -N for a child killed by signal N; a bare
    sys.exit(-N) wraps to 256-N (e.g. -15 -> 241). Shells report a
    signalled child as 128+N (143 for SIGTERM), so mirror that.
    """
    return 128 + (-rc) if rc < 0 else rc


def require_tool(name: str, hint: str) -> str:
    """Locate an executable or exit with an actionable message.

    Without this, a missing tool raises a bare FileNotFoundError traceback
    from subprocess rather than telling the user what to install.
    """
    found = shutil.which(name)
    if found is None:
        sys.exit(f"error: '{name}' not found on PATH. {hint}")
    return found


def required_install_tools(platform: str) -> list[tuple[str, str]]:
    """External tools the install sequence shells out to, per platform."""
    if platform == "linux":
        return [
            ("curl", "Install curl (e.g. 'sudo apt-get install curl')."),
            ("sudo", "This installer needs sudo for apt-get and usermod."),
        ]
    if platform == "windows":
        return [("winget", "Install 'App Installer' (winget) from the Microsoft Store.")]
    return [("brew", "Install Homebrew from https://brew.sh first.")]


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


def confirm_plan(platform: str, commands: list[Cmd]) -> bool:
    """Show what will run for this platform and ask the user to agree."""
    print(f"The following will be executed for platform '{platform}':")
    for cmd in commands:
        print(f"  {render(cmd)}")
    if platform == "linux":
        print(
            "\nNote: the steps above run under sudo (password prompt expected), "
            "and the kvm group change requires a re-login to take effect."
        )
    print()
    try:
        reply = input("Proceed? [y/N] ").strip().lower()
    except EOFError:
        reply = ""
    return reply in ("y", "yes")


def do_install(platform: str, dry_run: bool, assume_yes: bool = False) -> int:
    commands = build_setup_commands(platform, getpass.getuser())
    if not dry_run:
        if not assume_yes and not confirm_plan(platform, commands):
            print("aborted: user did not confirm.")
            return 1
        for name, hint in required_install_tools(platform):
            require_tool(name, hint)
    for cmd in commands:
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

    require_tool("gh", "Install the GitHub CLI, then run 'gh auth login'.")
    require_tool("sbx", "Run 'uv run sbx_setup.py' to install it first.")

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
    parser.add_argument(
        "--yes", "-y", action="store_true", help="skip the confirmation prompt"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.secret_gh:
        return do_secret_gh(args.dry_run)
    platform = normalise_platform(args.platform) if args.platform else current_platform()
    return do_install(platform, args.dry_run, assume_yes=args.yes)


if __name__ == "__main__":
    try:
        sys.exit(normalise_exit(main()))
    except KeyboardInterrupt:
        # Ctrl-C during an interactive install step should exit quietly.
        sys.exit(130)
