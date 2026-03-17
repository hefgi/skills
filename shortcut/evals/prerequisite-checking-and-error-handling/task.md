# Shortcut CLI Onboarding Guide

## Problem/Feature Description

A new developer joining a software team needs to start using Shortcut for issue tracking. They've been told to use the `short` CLI tool to interact with Shortcut from the terminal, but their laptop has an inconsistent development environment — some team members have the tool installed and working, others have an old version, and some don't have it at all. There have also been recent incidents where people's API tokens expired unexpectedly.

The team's DevOps lead wants a runbook document that outlines exactly what to check when setting up or troubleshooting the Shortcut CLI. It should cover what to do in each setup scenario a new developer might encounter, including handling version problems, authentication issues, Node.js compatibility, and network problems. The guide will be shared across the team so it must be precise and accurate.

## Output Specification

Produce a `shortcut-cli-runbook.md` document covering:

1. How to verify the CLI is installed and ready to use (including the exact command(s) to run)
2. What to do if the CLI is not installed (with installation steps)
3. What to do if the installed version is outdated
4. How to resolve authentication failures
5. What to do if the CLI crashes with import/module errors
6. How to handle network connectivity problems
7. What to do when looking up a story or epic ID returns a "not found" error

The runbook must be specific enough that a developer can follow it step by step without needing to ask follow-up questions.
