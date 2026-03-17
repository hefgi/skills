#!/bin/bash
set -e

echo "Setting up Shortcut CLI skill..."

# Check Node.js version (>= 20.19.0 required)
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    NODE_MINOR=$(echo "$NODE_VERSION" | cut -d. -f2)
    if [ "$NODE_MAJOR" -lt 20 ] || { [ "$NODE_MAJOR" -eq 20 ] && [ "$NODE_MINOR" -lt 19 ]; }; then
        echo ""
        echo "Warning: Node.js >= 20.19.0 is required. Found v${NODE_VERSION}."
        echo "Please upgrade Node.js before installing shortcut-cli."
        exit 0
    fi
else
    echo ""
    echo "Warning: Node.js is not installed. Node.js >= 20.19.0 is required."
    exit 0
fi

# Check if short CLI is installed
if ! command -v short &> /dev/null; then
    echo ""
    echo "Warning: 'short' CLI is not installed."
    echo ""
    echo "To install via Homebrew (recommended):"
    echo "  brew install shortcut-cli"
    echo ""
    echo "Or via npm:"
    echo "  npm install -g @shortcut-cli/shortcut-cli"
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

echo "Shortcut CLI is installed and authenticated."
