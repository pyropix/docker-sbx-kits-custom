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
