#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
"$PYTHON_BIN" -m unittest discover -s scripts -p 'test_*.py'
"$PYTHON_BIN" catalogue/build_catalogue.py
node scripts/verify-catalogue.cjs
node scripts/verify-route-motion.cjs
node scripts/verify-source-links.cjs
node scripts/verify-browsing.cjs
node --check dist/app.js
git diff --check
