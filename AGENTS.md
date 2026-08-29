# AGENTS.md

This project provides custom kits for [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/).
The sbx custom kits are based on [sbx-kits-contrib](https://github.com/docker/sbx-kits-contrib).

## Kit Author Skill

Load skill [kit-author](https://github.com/docker/sbx-kits-contrib/tree/main/skills/kit-author) when adding new or improving existing sbx kits.

## Git Commit Guidelines

Use conventional commit format.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `pyropix/docker-sbx-kits-custom`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, used verbatim as label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
