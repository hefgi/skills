# Shortcut Assistant Script

## Problem/Feature Description

A development team uses Shortcut for project management and wants to automate how they look up project items. Their team lead has bookmarked several Shortcut URLs and frequently pastes them into chat conversations alongside quick numeric references and keyword searches. The lead wants a shell script that acts as a Shortcut assistant — it should accept any of these different reference styles and automatically look up the right information.

The team currently wastes time copying IDs out of URLs or typing full commands. They want a script that handles the following cases in a single unified entry point: pasting a Shortcut story URL, pasting an epic URL, typing just a ticket number, typing "my" to see their own work, typing "list" for everything, or prefixing a search phrase with "search".

## Output Specification

Write a shell script `shortcut-assistant.sh` that accepts a single argument and routes it to the appropriate Shortcut CLI operation. The script should:

- Handle all the common argument patterns described above
- Print the results of each operation to stdout
- Check that the CLI is ready to use before attempting any operations, exiting with a helpful message if not

Also produce a `routing-log.md` file that documents each argument pattern the script handles, the CLI command it maps to, and a one-sentence explanation of the routing logic.

The script should be executable and work as: `./shortcut-assistant.sh "<argument>"`
