# AI Email Management Tool

An intelligent email management tool powered by Claude AI that helps you organize, categorize, and search through your emails using natural language.

## Features

- **Multi-Provider Support**: Connect to both Gmail (OAuth2) and IMAP email providers
- **AI-Powered Categorization**: Automatically categorize emails into urgent, important, newsletters, receipts, social, and can_wait
- **Smart Summarization**: Generate concise summaries with key points and action items
- **Natural Language Search**: Search your emails using plain English queries
- **Local SQLite Cache**: Fast local caching with full-text search
- **Beautiful CLI**: Rich terminal interface with colors and formatting

## Prerequisites

- Python 3.8 or higher
- Gmail API credentials (for Gmail access)
- Anthropic API key (for Claude AI)
- IMAP credentials (for non-Gmail accounts)

## Installation

1. **Clone the repository**:
   ```bash
   cd ~/personal-projects
   git clone https://github.com/nakata7193/AI-email-management-tool.git
   cd AI-email-management-tool
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your credentials:
   ```bash
   # Gmail API (optional)
   GMAIL_CREDENTIALS_FILE=credentials.json
   GMAIL_TOKEN_FILE=token.json

   # IMAP (optional)
   IMAP_SERVER=imap.gmail.com
   IMAP_PORT=993
   IMAP_EMAIL=your.email@gmail.com
   IMAP_PASSWORD=your_app_specific_password

   # Claude API (required)
   ANTHROPIC_API_KEY=sk-ant-your-api-key-here
   ```

5. **Set up Gmail API** (if using Gmail):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download `credentials.json` and place it in the project root

## Usage

### Authentication Setup

**Gmail OAuth2**:
```bash
python main.py setup --provider gmail
```
This opens a browser for OAuth2 authentication.

**IMAP**:
```bash
python main.py setup --provider imap
```
Ensure IMAP credentials are in `.env` file.

### Fetch Emails

Fetch emails from Gmail:
```bash
python main.py fetch --provider gmail --limit 50
```

Fetch unread emails from IMAP:
```bash
python main.py fetch --provider imap --unread-only
```

Fetch from all configured providers:
```bash
python main.py fetch --provider all --limit 100
```

### View Inbox

View all emails:
```bash
python main.py inbox
```

View only unread emails:
```bash
python main.py inbox --unread
```

Filter by category:
```bash
python main.py inbox --category urgent
```

### Categorize Emails

Automatically categorize all uncategorized emails:
```bash
python main.py categorize-all
```

Limit processing:
```bash
python main.py categorize-all --limit 50
```

### Summarize Email

Get AI summary of a specific email:
```bash
python main.py summarize <email_id>
```

Example:
```bash
python main.py summarize 18d4f8e...
```

### Natural Language Search

Search using plain English:
```bash
python main.py search "receipts from amazon last month"
python main.py search "unread emails from my boss"
python main.py search "important messages about the project"
```

### View Statistics

Display email statistics:
```bash
python main.py stats
```

### Clean Old Emails

Remove old emails from cache:
```bash
python main.py clean --days 30
```

## Project Structure

```
AI-email-management-tool/
├── main.py                    # CLI entry point
├── config.py                  # Configuration management
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── providers/                # Email provider implementations
│   ├── base.py              # Abstract EmailProvider interface
│   ├── gmail.py             # Gmail API client
│   └── imap.py              # IMAP client
├── storage/                  # Database layer
│   ├── cache.py             # SQLite caching
│   └── schema.sql           # Database schema
├── ai/                       # Claude AI integration
│   ├── categorizer.py       # Email categorization
│   ├── summarizer.py        # Email summarization
│   └── search.py            # Natural language search
├── parsers/                  # Email parsing utilities
│   └── email_parser.py      # HTML/text parsing
└── utils/                    # Helper utilities
    └── formatting.py        # Rich terminal formatting
```

## Email Categories

- **urgent** 🔴: Requires immediate action or response
- **important** 🟡: Needs attention soon but not urgent
- **newsletter** 📰: Bulk, marketing, or subscription content
- **receipts** 🧾: Purchase confirmations, invoices, orders
- **social** 💬: Social media notifications and updates
- **can_wait** ⏸️: Low priority, can be addressed later

## Security Notes

- All credentials are stored in `.env` (not committed to git)
- Gmail OAuth tokens are stored locally in `token.json`
- For IMAP, use app-specific passwords (not your actual password)
- Email cache is stored in local SQLite database
- All data stays on your machine

## Troubleshooting

### Gmail Authentication Issues

If you get authentication errors:
1. Ensure `credentials.json` is in the project root
2. Delete `token.json` and re-authenticate
3. Check that Gmail API is enabled in Google Cloud Console

### IMAP Connection Issues

If IMAP fails to connect:
1. Verify IMAP is enabled on your email account
2. Use app-specific password (for Gmail, Yahoo, etc.)
3. Check firewall isn't blocking port 993

### Claude API Errors

If AI features fail:
1. Verify your Anthropic API key is correct
2. Check you have API credits available
3. Review rate limits if seeing throttling errors

## Development

Run tests:
```bash
pytest tests/
```

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python main.py <command>
```

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/nakata7193/AI-email-management-tool/issues)
- Check existing issues for solutions

## Roadmap

- [ ] Email thread analysis
- [ ] Draft response generation
- [ ] Background sync daemon
- [ ] Web dashboard interface
- [ ] Email rules and filters
- [ ] Attachment handling
- [ ] Multiple account management
