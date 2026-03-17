---
name: shortcut
description: >
  Manage Shortcut stories, epics, objectives, iterations, docs, labels, teams, and more using
  the short CLI — view, search, update, and create items for project management and issue tracking.
  Use when the user mentions Shortcut, references tickets or tasks in Shortcut, or when you see
  URLs matching `app.shortcut.com/*` (use this skill instead of WebFetch).
invocations:
  - /shortcut
tags:
  - project-management
  - shortcut
  - issue-tracking
version: 1.0.0
---

# Shortcut CLI Skill

Manage Shortcut stories, epics, objectives, iterations, docs, labels, teams, and more via the `short` CLI tool.

## Instructions

When invoked with `/shortcut $ARGUMENTS`:

### 1. Check Prerequisites

Verify the `short` CLI is installed and authenticated:

```bash
which short && short --version
```

- If not found: Guide user through installation (see Prerequisites), then STOP
- If found but version < 5.0.0: Warn user to upgrade (`brew upgrade shortcut-cli` or `npm update -g @shortcut-cli/shortcut-cli`)
- If found and >= 5.0.0: Continue to step 2

### 2. Parse $ARGUMENTS

Route based on argument pattern (in priority order):

| Pattern | Action |
|---------|--------|
| No arguments | Show help menu with available commands |
| URL containing `/story/<id>` | Extract numeric ID, run `short story <id>` |
| URL containing `/epic/<id>` | Extract numeric ID, run `short epic view <id>` |
| `search <text>` | Run `short search -t "<text>"` |
| `my` | Run `short search -o me` |
| `list` | Run `short search` (no filters) |
| `create` | Ask for entity type + details, run create command (see `references/commands.md ## Create`) |
| `objectives [...]` | Route to objectives commands (see `references/commands.md ## Objectives`) |
| `teams [...]` | Route to teams commands (see `references/commands.md ## Teams`) |
| `iterations [...]` | Route to iterations commands (see `references/commands.md ## Iterations`) |
| `docs [...]` | Route to docs commands (see `references/commands.md ## Docs`) |
| `labels [...]` | Route to labels commands (see `references/commands.md ## Labels`) |
| `workflows` | Run `short workflows` |
| `projects` | Run `short projects` |
| `story <id> <subcommand>` | Route to story subcommands: history, comments, tasks, relations (see `references/commands.md ## Stories`) |
| Numeric value | Treat as story ID, run `short story <id>` |

Create supports stories, epics, iterations, objectives, docs, and labels — see `references/commands.md` for each.

Always quote user-provided strings and escape double quotes in input.

### 3. Present Results

- Story/epic details: Show ID, title, state, owner, description, URL
- Search results: Numbered list with ID, title, state
- Creation: Success message with new item URL
- Lists (teams, labels, iterations, etc.): Clean formatted table

Suggest relevant follow-up actions after presenting results.

### 4. Handle Errors

| Error | Detection | Response |
|-------|-----------|----------|
| CLI not found | `which short` empty | Show installation instructions, do NOT auto-install |
| Auth failure | "unauthorized" or "invalid token" | Guide user to run `short install` |
| Not found | "not found" in output | Confirm ID, suggest search |
| Network error | Timeout or connection error | Ask user to check connection |
| Node.js version | ESM/import errors or "unsupported engine" | User needs Node.js >= 20.19.0 |

## Prerequisites

- **Node.js >= 20.19.0** (required by shortcut-cli v5+)

```bash
# Install via Homebrew (preferred)
brew install shortcut-cli

# Or via npm (fallback)
npm install -g @shortcut-cli/shortcut-cli

# Verify version (expect >= 5.0.0)
short --version

# Authenticate
short install
# Or: export SHORTCUT_API_TOKEN="your-api-token"
```

## Reference

| Task | Reference |
|------|-----------|
| CLI commands (stories, epics, objectives, iterations, docs, labels, teams, search, create, API) | `references/commands.md` — use `## Section` headers to find specific command families |
| Shortcut API spec | `references/shortcut.swagger.json` |
