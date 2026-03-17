# Custom Story Relationship Management

## Problem/Feature Description

A backend team is cleaning up their Shortcut workspace after a major refactor. They need to link several stories together to reflect architectural dependencies and mark some older duplicates appropriately. They also want to pull a custom field definition to verify its ID before using it in automated story triage.

After reviewing what's available in their CLI tooling, they've found that some of these operations — specifically viewing raw custom field data and setting story relationships — aren't surfaced through the standard command set. They need a way to use the same authenticated CLI tool to make these lower-level calls without switching to a different client.

Write a shell script `story-relations.sh` that:
1. Retrieves the list of custom fields in the workspace
2. Creates a blocking relationship between story 1001 and story 1002 (1001 blocks 1002)
3. Retrieves the current details of story 1001 to confirm the change

## Output Specification

Produce:
- `story-relations.sh` — the executable script with all three operations
- `api-reference.md` — a document describing which API endpoints were used, the HTTP methods, any request body fields, and how you identified the correct endpoints

The script should include comments explaining what each `short api` call does.
