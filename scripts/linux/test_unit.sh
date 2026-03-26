#!/usr/bin/env bash
# test_unit.sh — run unit tests for hub_enrichment module
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Running hub_enrichment unit tests..."

# Smoke test: verify enrich_post.py parses and exits with usage error (not import error)
cd "$MODULE_ROOT"
output=$(python3 hub_enrichment/enrich_post.py 2>&1 || true)
if echo "$output" | grep -q "Usage:"; then
    echo "  ✓ enrich_post.py argument validation works"
else
    echo "  ✗ Unexpected output: $output"
    exit 1
fi

# Verify all required imports are available
python3 -c "
import anthropic
import frontmatter
import requests
import json, os, sys, logging
print('  ✓ All required imports available')
"

echo "Unit tests passed."
