# Hefgi Skills

A collection of Claude Code skills for various tools and services.

## Skills

| Skill | Description | Invocation |
|-------|-------------|------------|
| [shortcut](./shortcut/) | Interact with Shortcut stories and epics via the `short` CLI | `/shortcut` |

## Installation

Install skills in Claude Code using the plugin marketplace:

```bash
claude plugin marketplace add hefgi/skills
claude plugin install <skill-name>
```

## Adding a New Skill

1. Create a new folder: `my-skill/`
2. Add a `SKILL.md` with frontmatter (name, description, invocations, tags, version)
3. Add any reference files in `my-skill/reference/`
4. Register the skill in `.claude-plugin/marketplace.json`
5. Optionally add a setup script and register it in `conductor.json`
