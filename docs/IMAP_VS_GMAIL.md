# Email Operations: IMAP vs Gmail API

## Summary

**Yes, you can delete and move emails directly through IMAP!** IMAP actually gives you **more direct control** over email manipulation compared to Gmail's API. Both providers now support full email lifecycle operations.

## Operation Comparison

| Operation | IMAP | Gmail API | Notes |
|-----------|------|-----------|-------|
| **Read emails** | ✅ RFC822 fetch | ✅ messages.get | Both work well |
| **Mark read** | ✅ +FLAGS \\Seen | ✅ removeLabelIds: UNREAD | IMAP simpler |
| **Mark unread** | ✅ -FLAGS \\Seen | ✅ addLabelIds: UNREAD | Both supported |
| **Delete** | ✅ +FLAGS \\Deleted | ✅ messages.trash() | IMAP marks, Gmail moves |
| **Permanent delete** | ✅ EXPUNGE | ✅ messages.delete() | Both supported |
| **Move folders** | ✅ COPY + DELETE | ✅ Modify labels | Different concepts |
| **Archive** | ❌ N/A | ✅ Remove INBOX label | Gmail-specific |
| **Flag/Star** | ✅ +FLAGS \\Flagged | ✅ Add STARRED label | Both supported |
| **Spam** | ⚠️ Server-dependent | ✅ Add SPAM label | Gmail explicit |
| **List folders** | ✅ LIST command | ✅ labels.list() | IMAP=folders, Gmail=labels |
| **Batch ops** | ❌ One-by-one | ✅ batchModify() | Gmail faster for bulk |
| **Search** | ⚠️ Basic IMAP SEARCH | ✅ Powerful query syntax | Gmail much better |

## Implementation Details

### IMAP Operations

#### Available Methods (providers/imap.py)

```python
from providers.imap import IMAPProvider

imap = IMAPProvider(config)
imap.connect()

# Read operations
emails = imap.fetch_emails(limit=100, unread_only=False)
email = imap.get_email_by_id("message-id")
folders = imap.list_folders()  # ['INBOX', 'Sent', 'Drafts', 'Archive', ...]

# Mark read/unread
imap.mark_as_read("message-id")
imap.mark_as_unread("message-id")

# Delete operations
imap.delete_email("message-id", expunge=False)  # Mark for deletion
imap.delete_email("message-id", expunge=True)   # Delete immediately
imap.expunge_deleted()  # Permanently remove all marked emails

# Move operations
imap.move_email("message-id", "Archive")        # Move to Archive folder
imap.move_email("message-id", "Spam")           # Move to Spam

# Flag operations
imap.flag_email("message-id", flagged=True)     # Star
imap.flag_email("message-id", flagged=False)    # Unstar

imap.disconnect()
```

#### How IMAP "Move" Works

IMAP doesn't have a native "move" command. It's implemented as:
1. **COPY** - Copy email to destination folder
2. **STORE +FLAGS \\Deleted** - Mark original as deleted
3. **EXPUNGE** - Permanently remove marked emails

```python
# Behind the scenes:
def move_email(email_id, destination):
    self.connection.copy(msg_id, destination)      # Copy to dest
    self.connection.store(msg_id, '+FLAGS', '\\Deleted')  # Mark original
    self.connection.expunge()                       # Remove original
```

#### IMAP Delete Behavior

IMAP has a two-phase delete:
1. **Mark for deletion**: `+FLAGS \\Deleted` (reversible)
2. **Expunge**: Permanently remove (irreversible)

```python
# Soft delete (can undo)
imap.delete_email("msg-id", expunge=False)
# Email still in mailbox with \\Deleted flag

# Undo the delete
imap.connection.store(msg_id, '-FLAGS', '\\Deleted')

# Hard delete (permanent)
imap.delete_email("msg-id", expunge=True)
# Email gone forever
```

### Gmail API Operations

#### Available Methods (providers/gmail.py)

```python
from providers.gmail import GmailProvider

gmail = GmailProvider(config)
gmail.connect()

# Read operations
emails = gmail.fetch_emails(limit=100, unread_only=False)
email = gmail.get_email_by_id("gmail-message-id")
labels = gmail.list_labels()  # System + custom labels

# Mark read/unread
gmail.mark_as_read("gmail-message-id")
gmail.mark_as_unread("gmail-message-id")

# Delete operations
gmail.delete_email("msg-id", permanent=False)  # Move to trash (recoverable 30 days)
gmail.delete_email("msg-id", permanent=True)   # Permanent delete
gmail.untrash_email("msg-id")                  # Restore from trash

# Move operations (label-based)
gmail.archive_email("msg-id")                  # Remove from INBOX
gmail.move_email("msg-id", 
    add_labels=['Important'],
    remove_labels=['INBOX'])
gmail.mark_as_spam("msg-id")                   # Move to SPAM folder

# Star operations
gmail.star_email("msg-id", starred=True)       # Add star
gmail.star_email("msg-id", starred=False)      # Remove star

# Advanced search
emails = gmail.search_gmail("from:user@example.com has:attachment after:2024/01/01")
sender_stats = gmail.analyze_top_senders(limit=5000)

gmail.disconnect()
```

#### Gmail Label System

Gmail uses **labels** instead of folders. An email can have multiple labels:

```python
# Traditional "folders" are labels:
'INBOX'      # Inbox folder
'SENT'       # Sent folder
'DRAFT'      # Drafts folder
'SPAM'       # Spam folder
'TRASH'      # Trash folder

# Special labels:
'UNREAD'     # Unread status
'STARRED'    # Starred/flagged
'IMPORTANT'  # Gmail's importance marker

# Custom labels:
'Work'       # User-created
'Personal'   # User-created
```

**Example: Archive vs Delete vs Move**

```python
# Archive (remove from inbox, keep accessible)
gmail.move_email("msg-id", remove_labels=['INBOX'])

# Move to custom label
gmail.move_email("msg-id", 
    add_labels=['Work/Projects'], 
    remove_labels=['INBOX'])

# Trash (recoverable for 30 days)
gmail.delete_email("msg-id", permanent=False)

# Permanent delete (gone forever)
gmail.delete_email("msg-id", permanent=True)
```

## Performance Considerations

### IMAP
- **Pros:**
  - Direct folder access
  - True folder hierarchy
  - Works with any email provider
  - Simple flag-based operations
  
- **Cons:**
  - No batch operations (one email at a time)
  - Slower for bulk operations
  - Network overhead per operation
  - Some servers rate-limit aggressively

### Gmail API
- **Pros:**
  - Batch operations (modify 1000+ emails at once)
  - Powerful search
  - Efficient pagination
  - Better rate limits
  
- **Cons:**
  - Label-based (not true folders)
  - Gmail-only
  - OAuth2 complexity
  - API quota limits

## Usage Examples

### Example 1: Bulk Archive Old Newsletters

**IMAP:**
```python
imap = IMAPProvider(config)
imap.connect()

# Get emails
emails = imap.fetch_emails(limit=1000)

# Filter newsletters (in your app logic)
newsletters = [e for e in emails if is_newsletter(e)]

# Archive one by one
for email in newsletters:
    imap.move_email(email.id, "Archive")
    # ~1-2 seconds per email = 30+ minutes for 1000 emails

imap.disconnect()
```

**Gmail API:**
```python
gmail = GmailProvider(config)
gmail.connect()

# Batch operation (much faster)
msg_ids = gmail.search_gmail("category:promotions older_than:30d", limit=1000)
newsletter_ids = [e.id for e in msg_ids]

# Archive 50-100 emails per API call
for i in range(0, len(newsletter_ids), 100):
    batch = newsletter_ids[i:i+100]
    for msg_id in batch:
        gmail.archive_email(msg_id)
    # ~5 seconds per 100 emails = ~1 minute for 1000 emails

gmail.disconnect()
```

### Example 2: Delete Emails from Specific Sender

**IMAP:**
```python
imap = IMAPProvider(config)
imap.connect()

# IMAP doesn't have good server-side filtering
# Must fetch and filter client-side
emails = imap.fetch_emails(limit=5000)
spam_emails = [e for e in emails if 'spam@example.com' in e.sender]

for email in spam_emails:
    imap.delete_email(email.id, expunge=True)

imap.disconnect()
```

**Gmail API (Better):**
```python
gmail = GmailProvider(config)
gmail.connect()

# Server-side filtering (much faster)
spam_emails = gmail.search_gmail("from:spam@example.com", limit=1000)

for email in spam_emails:
    gmail.delete_email(email.id, permanent=False)  # Move to trash

gmail.disconnect()
```

### Example 3: Smart Auto-Archive

```python
from services.email_service import EmailService
from ai.categorizer import EmailCategorizer

# Works with both IMAP and Gmail
service = EmailService(cache)
categorizer = EmailCategorizer(api_key)

# Categorize emails
for _, _, email_data, category in service.categorize_uncategorized_emails(categorizer, 100):
    
    # Auto-archive low-priority categories
    if category in ['newsletter', 'social', 'can_wait']:
        
        if using_gmail:
            gmail.archive_email(email_data['id'])
        else:
            imap.move_email(email_data['id'], 'Archive')
```

## Recommendations

### Use IMAP when:
- ✅ You need to support multiple email providers
- ✅ You want true folder hierarchies
- ✅ You're doing single-email operations
- ✅ You want direct protocol control

### Use Gmail API when:
- ✅ You're Gmail-only
- ✅ You need bulk operations (100+ emails)
- ✅ You need advanced search
- ✅ You want better performance

### Best Practice:
Use the **abstraction layer** we've built - both providers now support the same operations, so you can write provider-agnostic code:

```python
# Works with both Gmail and IMAP
def archive_old_newsletters(provider: EmailProvider):
    """Archive newsletters older than 30 days."""
    emails = provider.fetch_emails(limit=1000)
    
    for email in emails:
        if is_newsletter(email) and is_older_than_30_days(email):
            if isinstance(provider, GmailProvider):
                provider.archive_email(email.id)
            else:  # IMAP
                provider.move_email(email.id, 'Archive')
```

## Security Considerations

### IMAP
- ⚠️ Stores password in .env (less secure than OAuth2)
- ⚠️ No app-specific passwords by default
- ✅ Standard protocol, widely audited

### Gmail API
- ✅ OAuth2 with token refresh
- ✅ Scoped permissions
- ✅ Can revoke access from Google Account settings
- ⚠️ Requires Google Cloud project setup

## Conclusion

**Both IMAP and Gmail API now support full email lifecycle management** in this project:
- ✅ Read, mark read/unread
- ✅ Delete (soft and permanent)
- ✅ Move to folders/labels
- ✅ Flag/star emails
- ✅ List folders/labels

Choose based on your needs:
- **IMAP** = Universal, direct, simple
- **Gmail API** = Fast, powerful, Gmail-specific
