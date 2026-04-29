#!/usr/bin/env bash
# workflow.sh — Fetch, categorize, and organize emails end to end
#
# Usage:
#   ./workflow.sh                        # uses active profile, 10 emails
#   ./workflow.sh --profile atanas       # specific profile
#   ./workflow.sh --limit 50             # different batch size
#   ./workflow.sh --dry-run              # organize step shows preview only
#   ./workflow.sh --profile atanas --limit 20 --dry-run

set -euo pipefail

PROFILE=""
LIMIT=10
DRY_RUN=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --limit)   LIMIT="$2";   shift 2 ;;
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PROFILE_FLAG=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_FLAG="--profile $PROFILE"
fi

echo "========================================"
echo " AI Email Workflow"
echo "========================================"
[[ -n "$PROFILE" ]] && echo " Profile : $PROFILE" || echo " Profile : (active)"
echo " Limit   : $LIMIT emails"
[[ -n "$DRY_RUN" ]] && echo " Mode    : dry run (organize step only)" || echo " Mode    : live"
echo "========================================"
echo ""

# Step 1: Fetch
echo "► Step 1/3 — Fetching $LIMIT emails..."
python main.py $PROFILE_FLAG fetch --provider gmail --limit "$LIMIT"
echo ""

# Step 2: Categorize
echo "► Step 2/3 — Categorizing with AI (batch of $LIMIT in one API call)..."
python main.py $PROFILE_FLAG categorize --limit "$LIMIT"
echo ""

# Step 3: Organize
if [[ -n "$DRY_RUN" ]]; then
    echo "► Step 3/3 — Organizing (dry run — no changes to Gmail)..."
else
    echo "► Step 3/3 — Organizing: applying Gmail labels and moving out of inbox..."
fi
python main.py $PROFILE_FLAG organize $DRY_RUN --limit "$LIMIT"
echo ""

echo "========================================"
echo " Done!"
echo "========================================"
