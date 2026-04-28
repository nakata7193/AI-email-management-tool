# 🎉 User-Based Data Directory - Setup Complete!

Your data directory now uses a **user-based organization** where each user has their own isolated directory.

## ✅ New Structure

```
data/
├── atanas/                    ← User directory
│   ├── credentials.json       ← Gmail OAuth2 credentials
│   ├── token.json            ← Authentication token
│   └── email_cache.db        ← Database (38,654 emails)
```

## 🚀 Using the Profile System

### For Existing User (atanas)

```bash
# Use with --profile flag
python main.py --profile atanas stats
python main.py --profile atanas inbox
python main.py --profile atanas fetch --limit 100

# Or set as active profile
python main.py profile use atanas
python main.py stats  # Uses active profile
```

### Adding a New User

**Example: Adding user "maria"**

```bash
# 1. Create profile
python main.py profile create maria \
  --description "Maria's personal email" \
  --provider gmail

# 2. Create data directory
mkdir -p data/maria

# 3. Add Gmail credentials
# Download from: https://console.cloud.google.com
cp ~/Downloads/credentials.json data/maria/credentials.json

# 4. Authenticate (opens browser)
python main.py --profile maria setup --provider gmail

# 5. Fetch emails
python main.py --profile maria fetch --limit 100

# 6. Use normally
python main.py --profile maria inbox
python main.py --profile maria categorize-all
```

## 📁 Directory Structure Benefits

### Before (Old Structure) ❌
```
data/
├── email_cache_atanas.db      # User in filename
├── credentials_uni.json       # Confusing name
├── token_atanas.json         # User in filename
├── email_cache.db            # Which user?
└── (mixed files everywhere)
```

### After (New Structure) ✅
```
data/
├── atanas/                    # Clear user isolation
│   ├── credentials.json
│   ├── token.json
│   └── email_cache.db
├── maria/                     # Another user
│   ├── credentials.json
│   ├── token.json
│   └── email_cache.db
└── john/                      # Third user
    ├── credentials.json
    ├── token.json
    └── email_cache.db
```

## 🎯 Key Improvements

### 1. **Automatic Path Resolution**
No more manual path configuration! The profile system automatically uses:
- `data/{profile}/credentials.json`
- `data/{profile}/token.json`
- `data/{profile}/email_cache.db`

### 2. **Clean .env File**
Your `.env` is now much simpler:
```env
# Claude API
ANTHROPIC_API_KEY=xxx

# That's it! No more per-user paths needed
```

### 3. **Easy Multi-User Management**
```bash
# List all users
ls data/

# Check any user's stats
python main.py --profile atanas stats
python main.py --profile maria stats

# Switch between users
python main.py profile use atanas
python main.py profile use maria

# List all profiles
python main.py profile list
```

### 4. **Isolated Backups**
```bash
# Backup specific user
tar -czf atanas-backup-2026-04-29.tar.gz data/atanas/

# Restore user
tar -xzf atanas-backup-2026-04-29.tar.gz

# Remove old user
rm -rf data/olduser/
```

## 🔍 Quick Commands

### View User's Data
```bash
# Check email count
sqlite3 data/atanas/email_cache.db "SELECT COUNT(*) FROM emails;"

# View latest emails
sqlite3 data/atanas/email_cache.db \
  "SELECT subject, sender FROM emails ORDER BY received_date DESC LIMIT 5;"

# Check categories
sqlite3 data/atanas/email_cache.db \
  "SELECT category, COUNT(*) FROM emails GROUP BY category;"
```

### Manage Profiles
```bash
# List all profiles
python main.py profile list

# Create new profile
python main.py profile create NAME --description "DESC" --provider gmail

# Set active profile
python main.py profile use NAME

# Delete profile
python main.py profile delete NAME
```

## 🔐 Security

- ✅ Each user's data is isolated
- ✅ Entire `data/` directory excluded from git
- ✅ Easy to set permissions per user:
  ```bash
  chmod 700 data/atanas/  # Only you can access
  ```

## 📊 Migration Summary

### What Changed
1. ✅ Created `data/atanas/` directory
2. ✅ Moved files:
   - `email_cache_atanas.db` → `atanas/email_cache.db`
   - `credentials_uni.json` → `atanas/credentials.json`
   - `token_atanas.json` → `atanas/token.json`
3. ✅ Updated `config.py` to auto-detect user directories
4. ✅ Simplified `.env` (no more per-user paths!)
5. ✅ Tested: All 38,654 emails accessible via `--profile atanas`

### What Didn't Change
- ✅ Database schema (same)
- ✅ Email data (all preserved)
- ✅ CLI commands (work exactly the same)
- ✅ Profile system (enhanced, not replaced)

## ✨ Result

You now have:
- 🎯 **Clean organization** - One directory per user
- 🚀 **Easy scaling** - Add users in seconds
- 🔒 **Better security** - Isolated data per user
- 🛠️ **Simple management** - Clear structure
- 📦 **Easy backups** - Backup per user

**Your email management tool is now production-ready for multiple users!** 🎊
