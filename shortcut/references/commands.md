# Commands Reference

## View Story Details

```bash
short story <id>
```

## Update Story

```bash
# Update state/workflow
short story <id> -s "<state>"

# Update title
short story <id> -t "<title>"

# Update description
short story <id> -d "<description>"

# Add comment
short story <id> -c "<comment>"

# Open in browser
short story <id> -O
```

## Search Stories

```bash
# Search by text
short search -t "<text>"

# My assigned stories
short search -o me

# By workflow state
short search -s "<state>"

# By label
short search -l "<label>"
```

## Create Story

```bash
short create -t "<title>" -s "<state>" [options]

# Options:
#   -d "<description>"  - Story description
#   -y "<type>"         - Story type (feature, bug, chore)
```

## Epics

```bash
# List all epics
short epics

# View epic details
short epic view <id>

# Create epic
short epic create -n "<name>" [-d "<description>"]

# Update epic
short epic update <id> [-n "<name>"] [-d "<description>"]
```

## Raw API Access (Advanced)

For operations not covered by CLI commands, use direct API access:

```bash
# GET request
short api <path>

# POST request
short api <path> -X POST -f "key=value"

# PUT request
short api <path> -X PUT -f "key=value"

# DELETE request
short api <path> -X DELETE
```

Reference the Swagger spec at `references/shortcut.swagger.json` for available endpoints.
