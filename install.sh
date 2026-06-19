#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/claude_usage.py"

mkdir -p "$INSTALL_DIR"
ln -sf "$SCRIPT" "$INSTALL_DIR/claude-usage-tool"
chmod +x "$SCRIPT"

echo "✓ Installed claude-usage-tool -> $INSTALL_DIR/claude-usage-tool"

if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo ""
    echo "  $INSTALL_DIR is not in your PATH. Add it:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
fi
