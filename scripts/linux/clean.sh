#!/usr/bin/env bash
# clean.sh — remove build artifacts for hub_enrichment module
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Cleaning hub_enrichment build artifacts..."
find "$MODULE_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$MODULE_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "$MODULE_ROOT" -name "*.pyc" -delete 2>/dev/null || true
echo "Clean complete."
