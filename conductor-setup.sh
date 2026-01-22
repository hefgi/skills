#!/bin/bash
set -e

echo "Setting up Shortcut CLI skill..."

# Check if short CLI is installed
if ! command -v short &> /dev/null; then
    echo ""
    echo "Warning: 'short' CLI is not installed."
    echo ""
    echo "To install via Homebrew (recommended):"
    echo "  brew install shortcut-cli"
    echo ""
    echo "Or via npm:"
    echo "  npm install -g shortcut-cli"
    echo ""
    echo "After installation, run 'short install' to authenticate."
    exit 0
fi

# Check if authenticated
if ! short search -o me &> /dev/null; then
    echo ""
    echo "Warning: 'short' CLI may not be authenticated."
    echo ""
    echo "Run 'short install' to set up authentication."
    echo "Or set the SHORTCUT_API_TOKEN environment variable."
    exit 0
fi

echo "Setup complete! Shortcut CLI is installed and authenticated."
