# AI Email Management Tool

An intelligent email management tool powered by Claude AI that helps you organize, categorize, and search through your emails using natural language.

## ✨ Features

- **Multi-Provider Support**: Gmail (OAuth2) and IMAP providers
- **Multiple Account Profiles**: Manage work, personal, and other email accounts with isolated data
- **AI-Powered Features**:
  - Smart email categorization (urgent, important, newsletter, receipts, social)
  - Natural language search
  - Email summarization with action items
  - Sender analysis
- **Efficient Processing**:
  - Parallel fetching with 10 concurrent workers
  - Batch processing with automatic retry
  - Network resilience with exponential backoff
- **Local Storage**: SQLite database with full-text search
- **Clean Architecture**: Refactored with dependency injection and design patterns

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
cd ~/personal-projects/AI-email-management-tool

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file:

```bash
# Required: Claude API key for AI features
ANTHROPIC_API_KEY=your-api-key-here

# Optional: Application settings
MAX_FETCH_EMAILS=100
CACHE_MAX_AGE_DAYS=30
```

### 3. Set Up Your First Profile

```bash
# Activate virtual environment
source venv/bin/activate

# Create a profile for your email account
# This automatically creates the data/myemail/ directory
python main.py profile create myemail \
  --description "My personal Gmail" \
  --provider gmail

# Download Gmail credentials from Google Cloud Console
# (see Gmail Setup section below)
cp ~/Downloads/credentials.json data/myemail/credentials.json

# Authenticate (opens browser)
python main.py --profile myemail setup --provider gmail

# Fetch your emails
python main.py --profile myemail fetch --limit 100

# View your inbox
python main.py --profile myemail inbox
```

## 📖 Usage

### Profile Management

Profiles allow you to manage multiple email accounts with isolated data.

```bash
# Create a new profile
python main.py profile create work \
  --description "Work email" \
  --provider gmail

# List all profiles
python main.py profile list

# Set active profile (default for all commands)
python main.py profile use work

# Use specific profile
python main.py --profile work inbox

# Delete a profile
python main.py profile delete oldaccount
```

### Fetching Emails

```bash
# Fetch emails (uses active profile)
python main.py fetch --provider gmail --limit 100

# Fetch from specific profile
python main.py --profile work fetch --limit 50

# Fetch only unread emails
python main.py fetch --unread-only --limit 100

# Large batch with parallel processing
python main.py fetch --limit 5000 --batch-size 100
```

### Viewing Emails

```bash
# View inbox
python main.py inbox

# View only unread
python main.py inbox --unread

# Filter by category
python main.py inbox --category urgent

# Limit results
python main.py inbox --limit 20
```

### AI Features

```bash
# Categorize all emails
python main.py categorize-all --limit 100

# Search with natural language
python main.py search "emails from my boss about project deadline"

# Summarize a specific email
python main.py summarize <email-id>

# View statistics
python main.py stats
```

### Gmail-Specific Features

```bash
# Direct Gmail search (uses Gmail's search syntax)
python main.py gmail-search "from:user@example.com has:attachment"

# Analyze top senders (fast, metadata only)
python main.py analyze-senders --top 20 --min-count 10

# Analyze all emails (may take 30-45 min for large inboxes)
python main.py analyze-senders --all
```

### Maintenance

```bash
# Clean old emails from cache
python main.py clean --days 30
```

## 🔧 Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable Gmail API:
   - Navigate to: **APIs & Services → Library**
   - Search for "Gmail API"
   - Click **Enable**
4. Configure OAuth consent screen:
   - Go to: **APIs & Services → OAuth consent screen**
   - User Type: **External** (unless you have Google Workspace)
   - Fill in app name and your email
   - Add scopes: `gmail.readonly` and `gmail.modify`
   - Add your email as a **test user**
5. Create credentials:
   - Go to: **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON file
6. Save credentials:
   ```bash
   # Save to your profile's data directory
   cp ~/Downloads/credentials.json data/yourprofile/credentials.json
   ```

## 📁 Project Structure

```
AI-email-management-tool/
├── main.py                    # CLI entry point
├── config.py                  # Configuration management
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (excluded from git)
│
├── data/                      # User data (excluded from git)
│   ├── {profile}/            # Profile-specific directories
│   │   ├── credentials.json  # Gmail OAuth2 credentials
│   │   ├── token.json       # Authentication token
│   │   └── email_cache.db   # SQLite database
│   └── README.md            # Data directory guide
│
├── ai/                       # AI components
│   ├── client.py            # AI client abstraction
│   ├── categorizer.py       # Email categorization
│   ├── summarizer.py        # Email summarization
│   └── search.py            # Natural language search
│
├── services/                 # Business logic layer
│   ├── container.py         # Dependency injection
│   └── email_service.py     # Email service orchestration
│
├── providers/                # Email providers
│   ├── base.py              # Base classes and protocols
│   ├── gmail.py             # Gmail provider
│   ├── imap.py              # IMAP provider
│   └── gmail_components/    # Gmail components
│       ├── authenticator.py # OAuth2 authentication
│       ├── parser.py        # Message parsing
│       ├── fetcher.py       # Email fetching
│       └── modifier.py      # Email modification
│
├── storage/                  # Data persistence
│   ├── cache.py             # SQLite operations
│   └── schema.sql           # Database schema
│
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md      # Architecture guide
│   ├── REFACTORING_SUMMARY.md
│   ├── USER_BASED_DATA_SETUP.md
│   └── PROJECT_STRUCTURE.md
│
├── scripts/                  # Utility scripts
├── archive/                  # Old/deprecated code
└── tests/                    # Test files
```

## 📊 Database Schema

```sql
CREATE TABLE emails (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT,
    received_date TIMESTAMP,
    has_attachments BOOLEAN,
    is_read BOOLEAN,
    provider TEXT,
    
    -- AI-generated fields
    category TEXT,
    category_reasoning TEXT,
    summary TEXT,
    action_items TEXT,
    
    labels TEXT,
    fetched_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search
CREATE VIRTUAL TABLE emails_fts USING fts5(
    subject, sender, recipient, body,
    content='emails',
    content_rowid='rowid'
);
```

## 🏗️ Architecture

The application follows clean architecture principles with clear separation of concerns:

```
CLI Layer (main.py)
    ↓
Container Layer (services/container.py)
    ↓
Service Layer (services/email_service.py)
    ↓
Storage/Providers/AI (storage/, providers/, ai/)
```

Key design patterns:
- **Dependency Injection**: Container manages object creation
- **Single Responsibility**: Each component has one clear purpose
- **Composition Over Inheritance**: Gmail provider composes specialized components
- **Protocol-Based Abstraction**: AI client abstraction for testability

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 🔐 Security

- All sensitive data (credentials, tokens, databases) stored in `data/` directory
- `data/` directory is excluded from git
- Each profile has isolated data in `data/{profile}/`
- Never commit `.env`, `credentials.json`, or `token.json` files

## 💡 Multiple Users Example

```bash
# Work email
python main.py profile create work --description "Work Gmail" --provider gmail
# Creates: data/work/ directory automatically

cp ~/work-credentials.json data/work/credentials.json
python main.py --profile work setup --provider gmail
python main.py --profile work fetch --limit 1000

# Personal email  
python main.py profile create personal --description "Personal Gmail" --provider gmail
# Creates: data/personal/ directory automatically

cp ~/personal-credentials.json data/personal/credentials.json
python main.py --profile personal setup --provider gmail
python main.py --profile personal fetch --limit 500

# Switch between profiles
python main.py profile use work
python main.py inbox  # Shows work inbox

python main.py profile use personal
python main.py inbox  # Shows personal inbox
```

## 🐛 Troubleshooting

### "ModuleNotFoundError" when running commands

**Solution:** Activate the virtual environment first:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
python main.py --help
```

### Gmail "Access blocked" error

**Solution:**
1. Go to Google Cloud Console → OAuth consent screen
2. Add your email as a **test user**
3. Make sure Gmail API is enabled

### Database shows 0 emails

**Solution:** Check you're using the correct profile:
```bash
# List profiles and their data
python main.py profile list
ls data/

# Use correct profile
python main.py --profile yourprofile stats
```

### Network errors during fetch

The tool automatically retries with exponential backoff. If errors persist:
- Check your internet connection
- Reduce `--batch-size` (default: 100)
- Reduce parallel workers by modifying the provider code

## 📝 Development

### Running Tests

```bash
source venv/bin/activate
pytest tests/
```

### Code Style

The codebase follows:
- PEP 8 style guide
- Type hints for better IDE support
- Comprehensive docstrings
- Design patterns for maintainability

## 🎯 Roadmap

- [ ] Web UI for easier email management
- [ ] More AI features (auto-reply suggestions, smart folders)
- [ ] Outlook/Exchange provider support
- [ ] Email threading and conversation view
- [ ] Advanced search filters
- [ ] Export to various formats
- [ ] Mobile notifications

## 📄 License

MIT License

## 🙏 Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/) for AI features
- Uses [Google Gmail API](https://developers.google.com/gmail/api) for Gmail integration
- Powered by SQLite for local storage

## 📚 Additional Documentation

- [Architecture Guide](docs/ARCHITECTURE.md) - Complete system architecture
- [Refactoring Summary](docs/REFACTORING_SUMMARY.md) - Design patterns applied
- [User-Based Data Setup](docs/USER_BASED_DATA_SETUP.md) - Multi-user configuration
- [Project Structure](docs/PROJECT_STRUCTURE.md) - Detailed file organization

---

**Need help?** Check the [docs/](docs/) directory for detailed guides or open an issue on GitHub.
