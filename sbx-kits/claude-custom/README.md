# claude-custom

A mixin kit that turns the built-in `claude` agent into an opinionated, ready-to-use
Claude Code sandbox. Compose it onto the `claude` agent and every session gets extra CLI
tools, pre-configured settings, a two-line status line, agent instructions, and a custom
slash command.

Based on [`claude-sbx-statusline`](https://github.com/docker/sbx-kits-contrib/tree/main/claude-sbx-statusline).

## What you get

- **Extra tools** — `fd-find`, `git-secrets`, `nano`, and `tmux`, plus a full `apt`
  upgrade and the latest Claude CLI (`claude update`).
- **Pre-configured settings** (`settings.json`) — model `sonnet` with an `opus` advisor,
  `auto` permission mode, guardrails (`git push` / `gh pr create` require approval;
  `git reset` / `git clean` denied), and a leaner UI (bundled skills, workflows, remote
  control, connectors, and artifacts disabled).
- **Two-line status line** — with information about the current sandbox.
- **Agent instructions** — a short `CLAUDE.md` telling Claude it's inside a sandbox and to
  use conventional commits.
- **Custom command** — `/git-group-commits`, an interactive helper that groups unstaged
  changes into atomic commits.

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
- **`files/home/CLAUDE.template.md`** is staged in the agent home, then moved to
  `$WORKSPACE_DIR/../CLAUDE.md` in the `startup` step — after the sandbox has finished
  writing its own files, so it isn't clobbered.

## Requirements

The status line and install step use `jq`, `git`, `awk`, and `hostname` — all present on
the `claude-code` base image. The install step also adds `fd-find`, `git-secrets`, `nano`,
and `tmux` via `apt`.

> **Note:** the status line does not verify it is running inside a sandbox. Don't install
> it into your host's Claude Code, or it will falsely claim you're sandboxed.

## Known issues

- **`apt` install step fails while the sandbox TUI is open.** The install step that adds
  `fd-find`, `git-secrets`, `nano`, and `tmux` via `apt-get` can fail when the sandbox TUI
  is open. Close the TUI before (re)building the kit so the `apt-get install` step can
  complete.
