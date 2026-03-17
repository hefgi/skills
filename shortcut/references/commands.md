# Commands Reference

## Stories

```bash
# View story details
short story <id>

# Open story in browser
short story <id> -O

# Update state/workflow
short story <id> -s "<state>"

# Update title
short story <id> -t "<title>"

# Update description
short story <id> -d "<description>"

# Add comment
short story <id> -c "<comment>"

# Update estimate
short story <id> -e <points>

# Set deadline
short story <id> --deadline "<YYYY-MM-DD>"

# Add/set followers
short story <id> --followers "<mention>"

# Set requester
short story <id> --requester "<mention>"

# Move to team
short story <id> --team "<team>"

# Archive story
short story <id> --archive

# Unarchive story
short story <id> --unarchive

# Create git branch for story
short story <id> -b

# Download file attachments
short story <id> --download
```

### Story Subcommands

```bash
# View story history
short story <id> history

# List story comments
short story <id> comments

# List story tasks
short story <id> tasks

# List sub-tasks (child stories)
short story <id> sub-tasks

# List story relations (blockers, related, duplicates)
short story <id> relations
```

## Search

```bash
# Search by text
short search -t "<text>"

# My assigned stories
short search -o me

# By owner mention name
short search -o "<mention>"

# By workflow state
short search -s "<state>"

# By label
short search -l "<label>"

# By epic ID
short search -e <epic_id>

# By iteration ID
short search -i <iteration_id>

# By story type (feature, bug, chore)
short search -y "<type>"

# Archived stories
short search -a

# Custom output format (Go template)
short search -f "{{.Id}} {{.Name}} {{.State}}"

# Combine filters
short search -o me -s "In Progress" -l "backend"
```

## Create

```bash
# Create story (minimum)
short create -t "<title>" -s "<state>"

# Full story creation
short create -t "<title>" -s "<state>" \
  -d "<description>" \
  -e <estimate> \
  -y "<type>" \
  --epic <epic_id> \
  --iteration <iteration_id> \
  --label "<label>" \
  --owner "<mention>" \
  --team "<team>" \
  --project "<project>"

# Options:
#   -t "<title>"         - Story title (required)
#   -s "<state>"         - Workflow state (required)
#   -d "<description>"   - Story description (markdown)
#   -e <points>          - Estimate points
#   -y "<type>"          - Story type: feature, bug, chore
#   --epic <id>          - Assign to epic
#   --iteration <id>     - Assign to iteration
#   --label "<label>"    - Add label (repeatable)
#   --owner "<mention>"  - Add owner (repeatable)
#   --team "<team>"      - Assign to team
#   --project "<project>" - Assign to project
```

## Epics

```bash
# List all epics
short epics

# Filter epics by title
short epics -t "<text>"

# Filter by archived status
short epics -a

# Filter by completion (done/not done)
short epics --completed
short epics --not-completed

# Filter by milestone
short epics --milestone "<name>"

# Filter by objective
short epics --objective "<name>"

# View epic details
short epic view <id>

# Create epic
short epic create -n "<name>" [-d "<description>"]

# Update epic name
short epic update <id> -n "<name>"

# Update epic description
short epic update <id> -d "<description>"

# Set epic state (to do, in progress, done)
short epic update <id> -s "<state>"

# Set epic deadline
short epic update <id> --deadline "<YYYY-MM-DD>"

# Set planned start date
short epic update <id> --planned-start "<YYYY-MM-DD>"

# Add owners
short epic update <id> --owner "<mention>"

# Add teams
short epic update <id> --team "<team>"

# Add labels
short epic update <id> --label "<label>"

# List stories in epic
short epic stories <id>

# List epic comments
short epic comments <id>
```

## Objectives

```bash
# List all objectives
short objectives

# Filter by state
short objectives -s "<state>"

# Filter by title
short objectives -t "<text>"

# Filter by completion
short objectives --completed
short objectives --not-completed

# View objective details
short objective view <id>

# Create objective
short objective create -n "<name>" [-d "<description>"]

# Update objective
short objective update <id> [-n "<name>"] [-d "<description>"] [-s "<state>"]

# List epics under an objective
short objective epics <id>
```

## Teams

```bash
# List all teams
short teams

# View team details
short team view <id>

# List stories for a team
short team stories <id>
```

## Labels

```bash
# List all labels
short labels

# Create a label
short label create -n "<name>" [-c "<color>"]

# Update a label
short label update <id> -n "<name>"

# View stories by label
short search -l "<label>"

# View epics by label
short epics --label "<label>"
```

## Custom Fields

```bash
# List all custom fields
short custom-fields

# View a specific custom field
short custom-field view <id>
```

## Iterations

```bash
# List all iterations
short iterations

# Filter by status (started, unstarted, done)
short iterations -s "<status>"

# Filter by team
short iterations --team "<team>"

# Show current iteration only
short iterations --current

# Filter by title
short iterations -t "<text>"

# View iteration details
short iteration view <id>

# Create iteration
short iteration create -n "<name>" --start "<YYYY-MM-DD>" --end "<YYYY-MM-DD>"

# Update iteration
short iteration update <id> [-n "<name>"] [--start "<YYYY-MM-DD>"] [--end "<YYYY-MM-DD>"]

# Delete iteration
short iteration delete <id>

# List stories in iteration
short iteration stories <id>
```

## Docs

```bash
# Search docs by title
short docs -t "<text>"

# Search docs by creator
short docs --creator "<mention>"

# Search docs user is following
short docs --following

# View doc content
short doc view <id>

# View doc as HTML
short doc view <id> --html

# Create doc from markdown
short doc create -t "<title>" -b "<body_markdown>"

# Create doc from HTML
short doc create -t "<title>" --html "<body_html>"

# Update doc
short doc update <id> [-t "<title>"] [-b "<body>"]

# Delete doc
short doc delete <id>
```

## Workflows

```bash
# Display all workflow states
short workflows
```

## Projects

```bash
# List all projects
short projects

# Filter by archived status
short projects -a

# Filter by title
short projects -t "<text>"
```

## Workspace

```bash
# List saved searches
short saved-searches

# Load a saved search (runs it)
short saved-search load <id>

# Delete a saved search
short saved-search delete <id>
```

## Raw API Access

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
