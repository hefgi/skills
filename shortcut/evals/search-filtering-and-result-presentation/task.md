# Sprint Status Dashboard Script

## Problem/Feature Description

A team lead wants to quickly get a snapshot of their team's work status at the start of each day. They need to see multiple views of the current work: backend bugs in progress, all work owned by a specific developer, and a full picture of available labels and active iterations. The lead currently runs these queries manually each morning but wants it automated into a single script that prints everything in an easy-to-scan format.

The team uses Shortcut for all their project tracking. The lead wants the dashboard to show different types of information in the most readable format for each — search results should be easy to scan in order, while reference data like labels and iterations should be easy to compare at a glance.

## Output Specification

Write a shell script `daily-dashboard.sh` that performs the following queries and prints the results:

1. All stories in "In Progress" state with the label "backend" owned by @alex
2. All stories in "Ready for Development" state (no owner filter)
3. All available labels in the workspace
4. All current iterations

The script should print a clear header before each section and format each type of output appropriately.

Also produce a `dashboard-design.md` file explaining the formatting choices made for each section and why that format was chosen for that type of data.
