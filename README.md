# docker-sbx-kits-custom

Custom kits and helper scripts for running AI agents with custom configuration inside [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/).

The custom kits in `sbx-kits/` are based on
[docker/sbx-kits-contrib](https://github.com/docker/sbx-kits-contrib).

## What is a Docker Sandbox?

Docker Sandboxes (`sbx`) run AI agents such as Claude Code in isolated,
disposable VMs with a mounted workspace. A **kit** is a reusable bundle of tools,
settings, and permissions that is composed onto an agent at launch via `--kit`.

### The `claude-custom` kit

A `mixin` kit (`sbx-kits/claude-custom/spec.yaml`) that layers onto the built-in
`claude` agent and provides:

- Extra CLI tools (`fd-find`, `git-secrets`, `nano`, `tmux`) and a `claude update`.
- A two-line Claude Code **status line** (`files/home/.claude/statusline.sh`) showing
  sandbox host, working directory, git branch, model, context usage, memory, load, and cost.
- Pre-configured settings baked from `settings.template.json`.
- A project `CLAUDE.md` and a `git-group-commits` slash command.
- Scoped network permissions for Claude endpoints and the Ubuntu/Docker apt repos.

See `sbx-kits/claude-custom/README.md` for full details.

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

## Known issues

- **`apt-get install` step fails while the sandbox TUI is open.** The `claude-custom` kit's
  install step that adds extra CLI tools via `apt-get` can fail when the sandbox TUI is
  open. Close the TUI before (re)building the kit so the `apt-get install` step can
  complete.

## References

- Docker Sandboxes documentation: https://docs.docker.com/ai/sandboxes/
- Contributed kits (basis for this repo): https://github.com/docker/sbx-kits-contrib
