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
    shift
fi

# Always remove the autosummary-generated stubs before building. These files
# are regenerated from the current package layout by ``autosummary_generate``,
# but sphinx does not delete stubs for modules that were renamed or removed.
# Leaving stale stubs behind produces spurious "failed to import" /
# "document isn't included in any toctree" warnings on every subsequent build.
rm -rf _autosummary

# Generate ignored documentation artifacts before Sphinx reads the table of contents.
python generate_class_hierarchy.py

# Generate the ignored model registry page from the live supported_models registry.
python generate_model_overview.py

jupyter-book build --keep-going --warningiserror "$@" .
