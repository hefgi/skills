# Batch Story Creation from Sprint Planning Notes

## Problem/Feature Description

A product team just finished their sprint planning session and took notes in a shared document. They now need to get all the planned work items into Shortcut as stories before the sprint begins. The planning notes contain story titles, descriptions, types (feature, bug, or chore), owners, labels, and which epic each belongs to — but they're all sitting in a text document that hasn't been acted on yet.

The engineering manager wants a shell script that reads these planning notes and creates the appropriate Shortcut stories, assigning them to the right epic and team members. The script should be runnable directly and produce readable output confirming what was created.

## Input Files

The following files are provided as inputs. Extract them before beginning.

=============== FILE: inputs/sprint-notes.md ===============
# Sprint 14 Planning Notes

## Stories to Create

### 1. Fix login timeout bug
- Type: bug
- Description: Users are being logged out after 5 minutes of inactivity instead of the configured 30 minutes. Needs investigation of session token refresh logic.
- Owner: @alex
- State: Ready for Development
- Label: authentication
- Epic ID: 441

### 2. Add dark mode toggle
- Type: feature
- Description: Add a user preference toggle in the settings page to switch between light and dark themes. Use the existing ThemeContext.
- Owner: @maria
- State: Ready for Development
- Label: ui
- Epic ID: 441

### 3. Update CI pipeline docs
- Type: chore
- Description: Update the README with current CI pipeline steps after the Jenkins to GitHub Actions migration last month.
- Owner: @alex
- State: Backlog
- Label: documentation

## Output Specification

Write a shell script `create-sprint-stories.sh` that creates each story above using the Shortcut CLI. The script should output a confirmation for each story created. Also produce a `creation-log.md` that records each story's title, the full CLI command used to create it, and the outcome.
