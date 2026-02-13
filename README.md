# Shortcut CLI Skill

A Claude skill for interacting with [Shortcut](https://shortcut.com) (formerly Clubhouse) stories and epics. Uses the official `shortcut-cli` tool.

## What's included

- **`shortcut/SKILL.md`** - Claude skill documentation for using the CLI
- **`.claude-plugin/marketplace.json`** - Marketplace definition for easy installation in Claude
- **`shortcut/reference/shortcut.swagger.json`** - Shortcut API reference for advanced operations

## Installation in Claude

Install this skill in Claude Code using the plugin marketplace:

```bash
claude plugin marketplace add hefgi/shortcut-cli-skill
claude plugin install shortcut
```

The skill will then be available for working with Shortcut stories directly through Claude.

## Prerequisites

### Install the Shortcut CLI

```bash
# Or via npm
npm install -g shortcut-cli
```

### Authentication

```bash
# Interactive setup
short install

# Or set environment variable
export SHORTCUT_API_TOKEN="your-api-token"
```

Get your API token from: https://app.shortcut.com/settings/account/api-tokens

## Quick Start

```bash
# Check installation
which short

# View a story
short story 12345

# Search stories
short search -t "bug fix"

# List your assigned stories
short search -o me
```

## Usage

The skill allows Claude to:

- **View stories/epics** - Fetch details by ID or URL
- **Search stories** - By text, owner, state, or label
- **Create stories** - With title, description, type, and state
- **Update stories** - Change state, title, description, or add comments
- **List workspace stories** - View all stories in your workspace

### Example Commands

```bash
# View story details
short story <id>

# Update story state
short story <id> -s "In Progress"

# Add comment
short story <id> -c "Working on this"

# Search by text
short search -t "authentication"

# My assigned stories
short search -o me

# Create story
short create -t "Fix login bug" -s "Backlog" -y bug

# View epic
short epic view <id>

# List all epics
short epics
```

### URL Detection

When Claude sees Shortcut URLs like:
- `https://app.shortcut.com/myorg/story/12345`
- `https://app.shortcut.com/myorg/epic/678`

It will automatically extract the ID and fetch the details using the skill.

## Advanced: Raw API Access

For operations not covered by CLI commands:

```bash
# GET request
short api <path>

# POST request
short api <path> -X POST -f "key=value"

# PUT request
short api <path> -X PUT -f "key=value"
```

Reference the Swagger spec at `shortcut/reference/shortcut.swagger.json` for available endpoints.

## Error Handling

| Error Type | Detection | Solution |
|------------|-----------|----------|
| CLI not found | `which short` returns empty | Install via `brew install shortcut-cli` |
| Auth failure | "unauthorized" or "invalid token" | Run `short install` or set `SHORTCUT_API_TOKEN` |
| Not found | "not found" in output | Verify the story/epic ID |

## Related

- [shortcut-cli](https://github.com/shortcut/shortcut-cli) - The official Shortcut CLI tool
- [Shortcut API Docs](https://developer.shortcut.com/api/rest/v3)
- [linear-cli-skill](https://github.com/Valian/linear-cli-skill) - Similar skill for Linear
