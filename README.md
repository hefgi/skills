# Hefgi Skills

A collection of AI coding agent skills for various tools and services.

## Skills

| Skill | Description | Invocation | Score |
|-------|-------------|------------|-------|
| [shortcut](./shortcut/) | Interact with Shortcut stories and epics via the `short` CLI | `/shortcut` | [![tessl](https://img.shields.io/endpoint?url=https%3A%2F%2Fapi.tessl.io%2Fv1%2Fbadges%2Fhefgi%2Fshortcut)](https://tessl.io/registry/hefgi/shortcut) |
| [ponder](./ponder/) | Build EVM blockchain data indexers using Ponder (ponder.sh) | `/ponder` | [![tessl](https://img.shields.io/endpoint?url=https%3A%2F%2Fapi.tessl.io%2Fv1%2Fbadges%2Fhefgi%2Fponder)](https://tessl.io/registry/hefgi/ponder) |
| [convergent-review](./convergent-review/) | Review → fix → re-review loop until clean, through a code lens, a security lens, or both | `/convergent-review` | [![tessl](https://img.shields.io/endpoint?url=https%3A%2F%2Fapi.tessl.io%2Fv1%2Fbadges%2Fhefgi%2Fconvergent-review)](https://tessl.io/registry/hefgi/convergent-review) |

## Installation

### Using Claude Code

```bash
claude plugin marketplace add hefgi/skills
claude plugin install <skill-name>
```

### Using Tessl

```bash
npx tessl i hefgi/shortcut
npx tessl i hefgi/ponder
npx tessl i hefgi/convergent-review
```

### Using Skills.sh

```bash
npx skills add https://github.com/hefgi/skills --skill shortcut
npx skills add https://github.com/hefgi/skills --skill ponder
npx skills add https://github.com/hefgi/skills --skill convergent-review
```

## Adding a New Skill

1. Create a new folder: `my-skill/`
2. Add a `SKILL.md` with frontmatter (name, description, invocations, tags, version)
3. Add a `tile.json` with the skill metadata (name, version, summary, skill path)
4. Add any reference files in `my-skill/references/`
5. Update the Skills table in this README
