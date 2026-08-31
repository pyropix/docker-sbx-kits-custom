# claude-custom

A mixin kit that turns the built-in `claude` agent into an opinionated, ready-to-use
Claude Code sandbox. Compose it onto the `claude` agent and every session gets extra CLI
tools, pre-configured settings, a two-line status line, agent instructions, and a custom
slash command.

Based on [`claude-sbx-statusline`](https://github.com/docker/sbx-kits-contrib/tree/main/claude-sbx-statusline).

## What you get

- **Extra tools** — `fd-find`, `git-secrets`, `nano`, and `tmux` (`jq` is also apt-installed
  defensively but already ships in the base image), plus the latest Claude CLI
  (`claude update`), and `prettier@3` for post-tool-use formatting.
- **Pre-configured settings** (`settings.json`) — model `sonnet` with an `opus` advisor,
  `auto` permission mode, guardrails (`git push` / `gh pr create` require approval;
  `git reset` / `git clean` denied), and a leaner UI (bundled skills, workflows, remote
  control, connectors, and artifacts disabled).
- **Prettier hook** — a `PostToolUse` hook auto-formats files after every Write/Edit.
  Supports `.js`, `.ts`, `.css`, `.html`, `.json`, `.yaml`, `.md`, and more. Errors are
  surfaced to stderr instead of being swallowed.
- **Two-line status line** — with information about the current sandbox.
- **Agent instructions** — a short `CLAUDE.md` telling Claude it's inside a sandbox and to
  use conventional commits.
- **Custom command** — `/git-group-commits`, an interactive helper that groups unstaged
  changes into atomic commits.
- **Optional internal CA certificate** — drop a `files/home/internal-ca.crt` next to this
  kit and uncomment the matching `install` step in `spec.yaml` to trust it inside the
  sandbox. Useful behind a corporate TLS-inspecting proxy.

## Quick start

Pair the mixin with the `claude` agent via `--kit`:

```console
$ sbx run claude --kit ./claude-custom .
```

## How it works

- **`files/home/.claude/statusline.sh`** is copied to `~/.claude/statusline.sh` at sandbox
  start and marked executable. It receives the session JSON on stdin and prints the two
  lines.
- **`files/home/.claude/settings.template.json`** carries the desired settings (with the
  `statusLine` block already baked in) under a non-managed name so the copy survives. The
  root `install` step renames it to `~/.claude/settings.json`, replacing the base image's,
  then `chown`s `~/.claude` back to `agent`.
- **`files/home/.claude/commands/git-group-commits.md`** is copied into place as the
  `/git-group-commits` slash command.
- **`files/home/CLAUDE.template.md`** is the canonical agent-instructions text for the
  sandbox. The `startup` step moves it to `$WORKSPACE_DIR/../CLAUDE.md` once per sandbox
  lifetime. Any host-side `CLAUDE.md` living next to a workspace is a derivative of this
  file; keep them in sync manually or let the sandbox overwrite it on first start.
- **`files/home/internal-ca.crt`** (not committed, listed in this kit's `.gitignore`) is
  picked up by an `install` step in `spec.yaml` that is commented out by default. Place a
  PEM-encoded certificate at that path and uncomment the step to have it installed to
  `/usr/local/share/ca-certificates/` and trusted via `update-ca-certificates` at build time.

- **`files/home/.claude/hooks/prettier-format.sh`** is the `PostToolUse` hook. It checks
  for `jq` and `prettier` before running; if either is missing it exits silently. Prettier
  failures surface to stderr (exit 0 so the Claude session continues).

## Requirements

The status line uses `git`, `awk`, `hostname`, and `jq` — all present on the `claude-code`
base image (`jq` is also in the install step's apt list, as a defensive pin against base
image drift, not because it's missing). The install step adds `fd-find`, `git-secrets`,
`nano`, and `tmux` via `apt`, and `prettier@3` via npm.

> **Note:** the status line does not verify it is running inside a sandbox. Don't install
> it into your host's Claude Code, or it will falsely claim you're sandboxed.

## Settings notes

- **`cleanupPeriodDays: 9999`** — effectively disables automatic conversation cleanup so
  that sandbox sessions are not silently truncated. Reduce this if you want periodic cleanup.
- **Unknown settings keys are silently ignored** by Claude Code. If a key in
  `settings.template.json` stops working, verify it against the current settings schema;
  a typo or removed key will not produce an error.
- **Windows prerequisite: Hyper-V / Hypervisor Platform** must be enabled before installing
  Docker Sandboxes on Windows. Enable it via _Settings → Optional features → Hyper-V_, or
  run `Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform` in an
  elevated PowerShell session. The installer does not check for this at runtime.

## Known issues

- **`apt` install step fails while the sandbox TUI is open.** The install step that adds
  `fd-find`, `git-secrets`, `nano`, and `tmux` via `apt-get` can fail when the sandbox TUI
  is open. Close the TUI before (re)building the kit so the `apt-get install` step can
  complete.
