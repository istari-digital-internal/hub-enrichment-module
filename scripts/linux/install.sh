#!/usr/bin/env bash
# install.sh — install Python dependencies for the hub_enrichment module
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Installing hub_enrichment dependencies..."
pip3 install --quiet -r "$MODULE_ROOT/requirements.txt"
echo "Install complete."
