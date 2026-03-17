---
name: shortcut
description: >
  Manage Shortcut stories, epics, tickets, and tasks using the short CLI — view, search, update,
  and create items for project management and issue tracking. Use when the user mentions Shortcut,
  references tickets or tasks in Shortcut, or when you see URLs matching `app.shortcut.com/*`
  (use this skill instead of WebFetch).
invocations:
  - /shortcut
tags:
  - project-management
  - shortcut
  - issue-tracking
version: 1.0.0
---

# Shortcut CLI Skill

Manage Shortcut stories and epics via the `short` CLI tool.

## Instructions

When invoked with `/shortcut $ARGUMENTS`:

### 1. Check Prerequisites

Verify the `short` CLI is installed and authenticated:

```bash
which short
```

- If not found: Guide user through installation (see Prerequisites), then STOP
- If found: Continue to step 2

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
| `create` | Ask for title + state, then run `short create -t "<title>" -s "<state>"` |
| Numeric value | Treat as story ID, run `short story <id>` |

Always quote user-provided strings and escape double quotes in input.

### 3. Present Results

- Story/epic details: Show ID, title, state, owner, description, URL
- Search results: Numbered list with ID, title, state
- Creation: Success message with new story URL

Suggest relevant follow-up actions after presenting results.

### 4. Handle Errors

| Error | Detection | Response |
|-------|-----------|----------|
| CLI not found | `which short` empty | Show installation instructions, do NOT auto-install |
| Auth failure | "unauthorized" or "invalid token" | Guide user to run `short install` |
| Not found | "not found" in output | Confirm ID, suggest search |
| Network error | Timeout or connection error | Ask user to check connection |

## Prerequisites

```bash
# Install via Homebrew (preferred)
brew install shortcut-cli

# Or via npm (fallback)
npm install -g shortcut-cli

# Authenticate
short install
# Or: export SHORTCUT_API_TOKEN="your-api-token"
```

## Reference

| Task | Reference |
|------|-----------|
| CLI commands (stories, epics, search, create, API) | `references/commands.md` |
| Shortcut API spec | `references/shortcut.swagger.json` |
