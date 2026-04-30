#!/usr/bin/env bash
# workflow.sh — Fetch, classify, and organize emails end to end
#
# Usage:
#   ./workflow.sh                        # uses active profile, 100 emails
#   ./workflow.sh --profile atanas       # specific profile
#   ./workflow.sh --limit 50             # different batch size
#   ./workflow.sh --since 2026/04/01     # only emails after this date
#   ./workflow.sh --dry-run              # organize step shows preview only
#   ./workflow.sh --verbose              # print per-email progress
#   ./workflow.sh --profile atanas --limit 20 --dry-run

set -euo pipefail

# Resolve main.py relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/.."
MAIN="$REPO_DIR/main.py"

if [[ ! -f "$MAIN" ]]; then
    echo "Error: main.py not found at $MAIN"
    exit 1
fi

# Always run from the repo root so relative paths (data/, email_config.json) resolve correctly
cd "$REPO_DIR"

# Use venv python if available, otherwise fall back to python3
if [[ -f "$REPO_DIR/venv/bin/python" ]]; then
    PYTHON="$REPO_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "Error: python3 not found"
    exit 1
fi

PROFILE=""
LIMIT=100
SINCE=""
DRY_RUN=""
VERBOSE=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --limit)   LIMIT="$2";   shift 2 ;;
        --since)   SINCE="$2";   shift 2 ;;
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --verbose) VERBOSE="--verbose"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PROFILE_FLAG=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_FLAG="--profile $PROFILE"
fi

SINCE_FLAG=""
if [[ -n "$SINCE" ]]; then
    SINCE_FLAG="--since $SINCE"
fi

echo "========================================"
echo " AI Email Workflow"
echo "========================================"
[[ -n "$PROFILE" ]] && echo " Profile : $PROFILE" || echo " Profile : (active)"
echo " Limit   : $LIMIT emails"
[[ -n "$SINCE" ]] && echo " Since   : $SINCE"
[[ -n "$DRY_RUN" ]] && echo " Mode    : dry run (organize step only)" || echo " Mode    : live"
echo "========================================"
echo ""

"$PYTHON" "$MAIN" $PROFILE_FLAG run --limit "$LIMIT" $SINCE_FLAG $DRY_RUN $VERBOSE
