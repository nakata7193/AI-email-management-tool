#!/bin/bash
#
# AI Email Management Tool - Complete Workflow Script
# ====================================================
# This script automates the entire email management pipeline:
# 1. Check total emails across all inboxes
# 2. Download all emails to local SQLite database
# 3. Run AI analysis on all emails (categorize, detect receipts, importance)
# 4. Organize emails into Gmail folders based on analysis
#
# Prerequisites:
# - Python 3.x installed
# - Gmail OAuth2 credentials configured
# - ANTHROPIC_API_KEY set in .env file
#
# Usage:
#   ./workflow.sh              # Run full workflow
#   ./workflow.sh --check      # Only check email counts
#   ./workflow.sh --fetch      # Only fetch emails
#   ./workflow.sh --analyze    # Only run AI analysis
#   ./workflow.sh --organize   # Only organize (dry run)
#   ./workflow.sh --help       # Show help
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_PATH="email_cache_atanas.db"
BATCH_SIZE=100       # Emails per fetch batch
AI_BATCH_SIZE=10     # Emails per AI API call
MAX_WORKERS=10       # Parallel fetch workers

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

print_header() {
    echo ""
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

check_prerequisites() {
    print_step "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check .env file
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create it with ANTHROPIC_API_KEY"
        exit 1
    fi

    # Check for API key in .env
    if ! grep -q "ANTHROPIC_API_KEY" .env; then
        print_error "ANTHROPIC_API_KEY not found in .env file"
        exit 1
    fi

    # Check Gmail credentials
    if [ ! -f "token_atanas.json" ] && [ ! -f "credentials_uni.json" ]; then
        print_error "Gmail credentials not found. Run: python3 main.py setup --provider gmail"
        exit 1
    fi

    print_success "All prerequisites met"
}

# -----------------------------------------------------------------------------
# Step 1: Check Email Counts
# -----------------------------------------------------------------------------

check_email_counts() {
    print_header "STEP 1: CHECKING EMAIL COUNTS"

    # Check database count
    if [ -f "$DB_PATH" ]; then
        DB_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails;" 2>/dev/null || echo "0")
        print_info "Emails in local database: $DB_COUNT"

        # Show breakdown by provider
        echo ""
        echo "Database breakdown:"
        sqlite3 "$DB_PATH" "SELECT provider, COUNT(*) as count FROM emails GROUP BY provider;" 2>/dev/null || true

        # Show analyzed vs unanalyzed
        ANALYZED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails WHERE ai_analyzed = 1;" 2>/dev/null || echo "0")
        UNANALYZED=$((DB_COUNT - ANALYZED))
        echo ""
        print_info "AI Analyzed: $ANALYZED"
        print_info "Not analyzed: $UNANALYZED"
    else
        print_info "No local database found. Will create on first fetch."
        DB_COUNT=0
    fi

    echo ""
    print_info "To see Gmail inbox count, the fetch step will query the Gmail API"
}

# -----------------------------------------------------------------------------
# Step 2: Fetch All Emails
# -----------------------------------------------------------------------------

fetch_emails() {
    print_header "STEP 2: FETCHING ALL EMAILS FROM GMAIL"

    print_step "Starting email fetch (this may take 30-60 minutes for 40K+ emails)..."
    print_info "Batch size: $BATCH_SIZE emails per commit"
    print_info "Workers: $MAX_WORKERS parallel connections"

    # Run the fetch command
    python3 main.py fetch --provider gmail --limit 50000 --batch-size $BATCH_SIZE

    # Verify count
    if [ -f "$DB_PATH" ]; then
        FINAL_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails;")
        print_success "Fetch complete. Total emails in database: $FINAL_COUNT"
    fi
}

# -----------------------------------------------------------------------------
# Step 3: Run AI Analysis
# -----------------------------------------------------------------------------

run_ai_analysis() {
    print_header "STEP 3: RUNNING AI ANALYSIS ON ALL EMAILS"

    if [ ! -f "$DB_PATH" ]; then
        print_error "Database not found. Run fetch step first."
        exit 1
    fi

    # Check how many need analysis
    TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails;")
    ANALYZED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails WHERE ai_analyzed = 1;")
    TO_ANALYZE=$((TOTAL - ANALYZED))

    print_info "Total emails: $TOTAL"
    print_info "Already analyzed: $ANALYZED"
    print_info "To analyze: $TO_ANALYZE"

    if [ "$TO_ANALYZE" -eq 0 ]; then
        print_success "All emails already analyzed!"
        return
    fi

    # Estimate time and API calls
    API_CALLS=$((TO_ANALYZE / AI_BATCH_SIZE))
    print_info "Estimated API calls: $API_CALLS (batch size: $AI_BATCH_SIZE)"
    print_info "This may take 30-90 minutes for 38K emails..."

    echo ""
    print_step "Starting AI analysis..."

    # Run batch analysis
    python3 ai_analyze_emails.py --batch $TO_ANALYZE $AI_BATCH_SIZE

    # Show final stats
    echo ""
    print_step "Analysis Statistics:"
    python3 ai_analyze_emails.py --stats
}

# -----------------------------------------------------------------------------
# Step 4: Organize Emails (Preview/Dry Run)
# -----------------------------------------------------------------------------

organize_emails() {
    print_header "STEP 4: ORGANIZING EMAILS INTO FOLDERS"

    if [ ! -f "$DB_PATH" ]; then
        print_error "Database not found. Run fetch step first."
        exit 1
    fi

    # Check analysis status
    ANALYZED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM emails WHERE ai_analyzed = 1;")

    if [ "$ANALYZED" -eq 0 ]; then
        print_error "No emails analyzed yet. Run analysis step first."
        exit 1
    fi

    print_info "Analyzed emails: $ANALYZED"
    echo ""

    # Show preview (dry run - NO DELETIONS as per user request)
    print_step "Organization Preview (DRY RUN - no changes will be made):"
    python3 organize_emails.py --preview

    echo ""
    print_info "This script does NOT delete emails automatically."
    print_info "To organize emails manually, run:"
    echo "  python3 organize_emails.py --execute --move-only  # Move to folders only"
    echo "  python3 organize_emails.py --execute              # Move + delete promotional"
}

# -----------------------------------------------------------------------------
# Show Help
# -----------------------------------------------------------------------------

show_help() {
    echo "AI Email Management Tool - Workflow Script"
    echo ""
    echo "Usage: ./workflow.sh [option]"
    echo ""
    echo "Options:"
    echo "  (no option)    Run full workflow (check -> fetch -> analyze -> organize preview)"
    echo "  --check        Only check email counts"
    echo "  --fetch        Only fetch emails from Gmail"
    echo "  --analyze      Only run AI analysis"
    echo "  --organize     Only show organization preview"
    echo "  --stats        Show current database statistics"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./workflow.sh              # Full workflow"
    echo "  ./workflow.sh --analyze    # Just run AI analysis"
    echo "  ./workflow.sh --stats      # Check current status"
}

# -----------------------------------------------------------------------------
# Show Statistics
# -----------------------------------------------------------------------------

show_stats() {
    print_header "DATABASE STATISTICS"

    if [ ! -f "$DB_PATH" ]; then
        print_error "Database not found."
        exit 1
    fi

    echo ""
    echo "=== Email Counts ==="
    sqlite3 "$DB_PATH" "
        SELECT
            COUNT(*) as total_emails,
            SUM(CASE WHEN ai_analyzed = 1 THEN 1 ELSE 0 END) as analyzed,
            SUM(CASE WHEN ai_analyzed = 0 OR ai_analyzed IS NULL THEN 1 ELSE 0 END) as not_analyzed
        FROM emails;
    "

    echo ""
    echo "=== By Content Type ==="
    sqlite3 "$DB_PATH" "
        SELECT content_type, COUNT(*) as count
        FROM emails
        WHERE ai_analyzed = 1
        GROUP BY content_type
        ORDER BY count DESC;
    "

    echo ""
    echo "=== Important Flags ==="
    sqlite3 "$DB_PATH" "
        SELECT
            SUM(CASE WHEN contains_receipt = 1 THEN 1 ELSE 0 END) as receipts,
            SUM(CASE WHEN requires_action = 1 THEN 1 ELSE 0 END) as action_required,
            SUM(CASE WHEN is_promotional = 1 THEN 1 ELSE 0 END) as promotional,
            SUM(CASE WHEN importance = 'high' THEN 1 ELSE 0 END) as high_importance
        FROM emails
        WHERE ai_analyzed = 1;
    "

    echo ""
    echo "=== By Importance ==="
    sqlite3 "$DB_PATH" "
        SELECT importance, COUNT(*) as count
        FROM emails
        WHERE ai_analyzed = 1
        GROUP BY importance
        ORDER BY count DESC;
    "
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

main() {
    print_header "AI EMAIL MANAGEMENT TOOL"
    echo "Started at: $(date)"

    check_prerequisites

    case "${1:-full}" in
        --check)
            check_email_counts
            ;;
        --fetch)
            fetch_emails
            ;;
        --analyze)
            run_ai_analysis
            ;;
        --organize)
            organize_emails
            ;;
        --stats)
            show_stats
            ;;
        --help|-h)
            show_help
            ;;
        full|"")
            # Full workflow
            check_email_counts
            fetch_emails
            run_ai_analysis
            organize_emails

            print_header "WORKFLOW COMPLETE"
            echo "Finished at: $(date)"
            print_success "All steps completed successfully!"
            echo ""
            print_info "Next steps:"
            echo "  1. Review the organization preview above"
            echo "  2. Run 'python3 organize_emails.py --execute --move-only' to move emails to folders"
            echo "  3. Manually review promotional emails before deletion"
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main with all arguments
main "$@"
