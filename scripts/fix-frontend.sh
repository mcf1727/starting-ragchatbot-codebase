#!/bin/bash
# Auto-fix frontend formatting and lint issues from the project root.
# Applies Prettier formatting and ESLint auto-fixes in place.

set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "=== Frontend Auto-Fix ==="
echo "Directory: $FRONTEND_DIR"
echo ""

cd "$FRONTEND_DIR"

# Ensure dependencies are installed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install --silent
fi

echo "--- Prettier (format) ---"
npx prettier --write "*.js" "*.css" "*.html"
echo ""

echo "--- ESLint (fix) ---"
npx eslint --fix *.js || true
echo ""

echo "=== Auto-fix complete ==="
