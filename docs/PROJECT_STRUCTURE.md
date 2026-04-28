# 📁 Project Structure

Clean and organized directory structure for the AI Email Management Tool.

## Root Directory

```
AI-email-management-tool/
├── .env                    # Environment variables (excluded from git)
├── .env.example           # Example environment configuration
├── .gitignore             # Git ignore patterns
├── README.md              # Main project documentation
├── config.py              # Configuration management
├── main.py                # CLI entry point
├── requirements.txt       # Python dependencies
│
├── ai/                    # AI components
│   ├── client.py          # AI client abstraction (NEW)
│   ├── categorizer.py     # Email categorization
│   ├── summarizer.py      # Email summarization
│   └── search.py          # Natural language search
│
├── services/              # Business logic layer
│   ├── container.py       # Dependency injection (NEW)
│   └── email_service.py   # Email service orchestration
│
├── providers/             # Email provider implementations
│   ├── base.py            # Base classes and protocols
│   ├── gmail.py           # Gmail provider (refactored)
│   ├── imap.py            # IMAP provider
│   └── gmail_components/  # Gmail components (NEW)
│       ├── authenticator.py  # OAuth2 authentication
│       ├── parser.py         # Message parsing
│       ├── fetcher.py        # Email fetching
│       └── modifier.py       # Email modification
│
├── storage/               # Data persistence layer
│   ├── cache.py           # SQLite cache implementation
│   └── schema.sql         # Database schema
│
├── parsers/               # Email content parsing
│   └── email_parser.py    # HTML/text parsing utilities
│
├── utils/                 # Utility functions
│   └── formatting.py      # Display formatting
│
├── tests/                 # Test files
│   ├── test_*.py          # Unit tests
│   └── results/           # Test results
│
├── docs/                  # Documentation (NEW)
│   ├── README.md          # Documentation index
│   ├── ARCHITECTURE.md    # Architecture guide
│   ├── REFACTORING_SUMMARY.md      # Refactoring details
│   ├── REFACTORING_COMPLETE.md     # Refactoring summary
│   └── IMAP_VS_GMAIL.md   # Provider comparison
│
├── data/                  # Data files (excluded from git, NEW)
│   ├── README.md          # Data directory guide
│   ├── *.db               # SQLite databases
│   ├── credentials*.json  # OAuth2 credentials
│   ├── token*.json        # Authentication tokens
│   └── *.txt              # Analysis reports
│
├── scripts/               # Utility scripts (NEW)
│   ├── README.md          # Scripts documentation
│   ├── test-setup.sh      # Testing setup
│   ├── test_move_emails.py # Email move tests
│   └── workflow.sh        # Development workflow
│
├── archive/               # Archived/deprecated code (NEW)
│   ├── README.md          # Archive documentation
│   ├── main_old.py        # Old main.py
│   ├── gmail_old.py       # Old GmailProvider (756 lines)
│   └── *.py               # Other deprecated files
│
└── venv/                  # Virtual environment (excluded from git)
```

## Directory Purposes

### Production Code (Main Application)

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| **Root** | Main entry points and config | `main.py`, `config.py` |
| **ai/** | AI-powered features | `client.py`, `categorizer.py`, `summarizer.py` |
| **services/** | Business logic layer | `container.py`, `email_service.py` |
| **providers/** | Email provider implementations | `gmail.py`, `imap.py` |
| **providers/gmail_components/** | Gmail specialized components | `authenticator.py`, `parser.py`, `fetcher.py`, `modifier.py` |
| **storage/** | Data persistence | `cache.py`, `schema.sql` |
| **parsers/** | Content parsing | `email_parser.py` |
| **utils/** | Utility functions | `formatting.py` |

### Supporting Directories

| Directory | Purpose | Git Status |
|-----------|---------|------------|
| **docs/** | Documentation | ✅ Committed |
| **tests/** | Unit and integration tests | ✅ Committed |
| **scripts/** | Development utilities | ✅ Committed |
| **archive/** | Deprecated code (reference only) | ✅ Committed |
| **data/** | Databases, credentials, reports | ❌ Excluded (.gitignore) |
| **venv/** | Python virtual environment | ❌ Excluded (.gitignore) |

## File Count Summary

### Before Cleanup
- **Root directory**: 28 files (messy!)
- Mixed: code, docs, scripts, data, archives

### After Cleanup
- **Root directory**: 7 files (clean!)
- Organized into logical directories
- Clear separation of concerns

## Navigation Guide

### For Users
1. Start with `README.md` for setup instructions
2. Run `main.py` for CLI commands
3. Configure via `.env` file

### For Developers
1. Read `docs/ARCHITECTURE.md` for system design
2. Check `services/` for business logic
3. See `providers/` for email implementations
4. Review `ai/` for AI features

### For Testing
1. Run tests from `tests/` directory
2. Use scripts in `scripts/` for utilities
3. Check `archive/` for old implementations

## Important Notes

### Security
- **`data/`** contains sensitive credentials - excluded from git
- Never commit `credentials*.json` or `token*.json`
- Keep `.env` file secure (not in git)

### Backups
While excluded from git, backup:
- `data/*.db` - your email cache
- `data/credentials*.json` - OAuth2 credentials
- `.env` - your configuration

### Archive
- Files in `archive/` are **not used** in current app
- Kept for reference and comparison only
- Safe to delete if you don't need history

## Clean Directory Structure ✨

Now organized with:
- ✅ Clear separation of production code, docs, data, and archives
- ✅ Only 7 files in root (was 28!)
- ✅ Logical grouping by purpose
- ✅ README in each directory explaining contents
- ✅ Proper .gitignore for sensitive data
- ✅ Easy to navigate and understand
