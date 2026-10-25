#!/usr/bin/env bash
# One-time helper to git-init this repo, create the initial commit, and
# (optionally) push to a fresh GitHub remote.
#
# Prerequisites:
#   - git installed       (apt install git  /  brew install git)
#   - gh CLI installed    (only for the optional GitHub remote step)
#
# Usage:
#   ./scripts/init_repo.sh                       # local repo only
#   ./scripts/init_repo.sh --github <repo-name>  # also creates a private GH repo and pushes
#
# Safe to re-run: each step checks before acting.

set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v git >/dev/null; then
    echo "ERROR: git is not installed. Install it first." >&2
    exit 1
fi

if [[ -d .git ]]; then
    echo "Git repo already initialised."
else
    echo "==> git init"
    git init -q
    git branch -M main
fi

# Sensible defaults if user hasn't configured global identity.
if ! git config user.email >/dev/null; then
    git config user.email "nse-pulse@local"
    git config user.name "NSE Pulse"
    echo "==> Set local git identity (override anytime with git config)."
fi

# Pre-commit (idempotent — install_hooks only writes if not present).
if command -v pre-commit >/dev/null; then
    echo "==> pre-commit install"
    pre-commit install --install-hooks
else
    echo "(skip) pre-commit not installed. Run: pip install pre-commit && pre-commit install"
fi

# Initial commit if nothing committed yet.
if [[ -z "$(git log --oneline -n1 2>/dev/null)" ]]; then
    git add -A
    git -c commit.gpgsign=false commit -m "Initial commit: NSE Pulse — scraper, preprocess, screener DSL, alerts, portfolio, backtester" -q
    echo "==> Created initial commit."
fi

# Optional GitHub remote.
if [[ "${1:-}" == "--github" && -n "${2:-}" ]]; then
    if ! command -v gh >/dev/null; then
        echo "ERROR: gh CLI required for --github. https://cli.github.com" >&2
        exit 1
    fi
    repo_name="$2"
    echo "==> Creating GitHub repo $repo_name (private)…"
    gh repo create "$repo_name" --private --source=. --remote=origin --push
    echo "==> Pushed."
fi

echo "Done. Status:"
git status --short
