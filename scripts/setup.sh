#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Setting up Hefgi Skills..."
echo ""

# Run each skill's setup script
for setup_script in "$SCRIPT_DIR"/setup-*.sh; do
    [ -f "$setup_script" ] && bash "$setup_script"
done

echo ""
echo "Setup complete!"
