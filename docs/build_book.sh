#!/usr/bin/env bash
#
# Build the H2Integrate Jupyter Book.
#
# By default this preserves the _build/ directory so jupyter-cache can skip
# re-executing notebooks and MyST cells whose source hasn't changed, which
# makes incremental local rebuilds much faster. Pass --clean to force a
# from-scratch build (e.g. after upgrading Sphinx/jupyter-book or changing
# execution config).
set -euo pipefail

# Always run from the docs/ directory so relative paths below work regardless
# of where the caller invoked this script from (e.g. repo root, CI, RTD).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "--clean" ]]; then
    rm -rf _build
fi

# Generate the interactive class hierarchy diagram
python generate_class_hierarchy.py

# Refresh the auto-generated section of docs/user_guide/model_overview.md from
# the live supported_models registry. Run this before jupyter-book so the
# rendered overview always matches what the package actually exposes.
python generate_model_overview.py

jupyter-book build --keep-going .
