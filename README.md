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

## Helper scripts

Run these from the repository root. Each script mounts the current working directory
into the sandbox and, where applicable, prompts to clean up the sandbox afterward.

| Script                                          | Purpose                                                      |
| ----------------------------------------------- | ------------------------------------------------------------ |
| `00_docker_sbx_setup.sh`                        | Install `docker-sbx`, configure KVM access, and `sbx login`. |
| `10_docker_sbx_secret_gh.sh`                    | Store a GitHub token as an `sbx` secret.                     |
| `20_docker_sbx_claude_nokit.sh`                 | Run Claude Code with no custom kit.                          |
| `21_docker_sbx_claude_mcp.sh`                   | Run Claude Code with the Microsoft Learn MCP server.         |
| `22_docker_sbx_claude_ssh.sh`                   | Create a sandbox and SSH into it.                            |
| `23_docker_sbx_claude_ssh_vscode.sh`            | Open a sandbox in VS Code over Remote-SSH.                   |
| `30_docker_sbx_claude_custom_kit.sh`            | Run Claude Code with the `claude-custom` kit.                |
| `31_docker_sbx_claude_custom_kit_bash.sh`       | Open a bash shell in a running custom-kit sandbox.           |
| `32_docker_sbx_claude_custom_kit_ssh.sh`        | Create a custom-kit sandbox and SSH into it.                 |
| `33_docker_sbx_claude_custom_kit_ssh_vscode.sh` | Open a custom-kit sandbox in VS Code over Remote-SSH.        |

## Quick start

```console
$ ./00_docker_sbx_setup.sh                 # one-time host setup
$ ./30_docker_sbx_claude_custom_kit.sh     # run Claude Code with the custom kit
```

## Known issues

- **`apt-get install` step fails while the sandbox TUI is open.** The `claude-custom` kit's
  install step that adds extra CLI tools via `apt-get` can fail when the sandbox TUI is
  open. Close the TUI before (re)building the kit so the `apt-get install` step can
  complete.

## References

- Docker Sandboxes documentation: https://docs.docker.com/ai/sandboxes/
- Contributed kits (basis for this repo): https://github.com/docker/sbx-kits-contrib
