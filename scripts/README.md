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

Most of these pairs use different sandbox names and can be run side by side
without interfering. Three do not: `./sbx_run.py --no-kit --mcp mslearn`,
`./sbx_run.py --no-kit --mode ssh` and `./sbx_run.py --mode ssh` derive the
same sandbox names as their bash counterparts (`claude-mcp`, `claude-ssh` and
`claude-custom-ssh`), so running one of those Python commands reaches the
same sandbox as the matching bash script instead of a separate one. Switching
to the Python scripts leaves any other old sandboxes running — remove them
once with `sbx ls` and `sbx rm`.
