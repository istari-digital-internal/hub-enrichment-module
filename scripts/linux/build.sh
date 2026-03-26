#!/usr/bin/env bash
# build.sh — build/package the hub_enrichment module
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Building hub_enrichment module..."

# Validate module manifest
cd "$MODULE_ROOT"
if command -v stari &>/dev/null; then
    stari module lint && echo "Manifest lint passed."
else
    echo "stari CLI not found — skipping manifest lint."
fi

# Verify entrypoint exists
if [ ! -f "$MODULE_ROOT/hub_enrichment/enrich_post.py" ]; then
    echo "ERROR: entrypoint hub_enrichment/enrich_post.py not found"
    exit 1
fi

echo "Build complete."
