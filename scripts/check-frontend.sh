#!/bin/bash
# Run all frontend code quality checks from the project root.
# Exit code mirrors the combined result: 0 = all pass, non-zero = failures found.

set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "=== Frontend Quality Checks ==="
echo "Directory: $FRONTEND_DIR"
echo ""

cd "$FRONTEND_DIR"

# Ensure dependencies are installed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install --silent
fi

echo "--- Prettier (format check) ---"
npx prettier --check "*.js" "*.css" "*.html"
echo ""

echo "--- ESLint (lint check) ---"
npx eslint *.js
echo ""

echo "=== All checks passed ==="
