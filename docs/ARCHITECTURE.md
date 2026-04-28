# Architecture Documentation

## New Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI LAYER (main.py)                         │
│                                                                     │
│  Responsibilities:                                                  │
│  • Parse command-line arguments                                    │
│  • Format and display results                                      │
│  • Get dependencies from container                                 │
│                                                                     │
│  Does NOT:                                                         │
│  • Create objects (delegated to container)                         │
│  • Manage connections (delegated to providers)                     │
│  • Access cache directly (goes through service layer)              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Uses
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│               CONTAINER LAYER (services/container.py)               │
│                                                                     │
│  Responsibilities:                                                  │
│  • Create and manage object lifecycle                              │
│  • Inject dependencies                                             │
│  • Lazy initialization (create only when needed)                   │
│                                                                     │
│  Properties:                                                       │
│  • cache → EmailCache                                              │
│  • email_service → EmailService                                    │
│  • ai_client → ClaudeClient                                        │
│  • categorizer → EmailCategorizer                                  │
│  • summarizer → EmailSummarizer                                    │
│  • searcher → EmailSearcher                                        │
│  • get_provider(type) → EmailProvider                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Creates & Injects
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SERVICE LAYER (services/email_service.py)              │
│                                                                     │
│  Responsibilities:                                                  │
│  • Business logic orchestration                                    │
│  • Input validation                                                │
│  • Coordinate between storage and AI                               │
│                                                                     │
│  Key Methods:                                                      │
│  • fetch_and_store_emails() - Fetch with batching                 │
│  • categorize_uncategorized_emails() - Bulk categorization        │
│  • search_emails() - Natural language search                       │
│  • get_email_summary() - Get or generate summary                   │
│  • get_emails() - Retrieve with validation                         │
│  • get_uncategorized_count() - Count uncategorized                 │
└─────────────────────────────────────────────────────────────────────┘
                    │                                    │
                    │ Uses                               │ Uses
                    ▼                                    ▼
    ┌────────────────────────────┐      ┌────────────────────────────┐
    │  STORAGE LAYER             │      │  AI LAYER                  │
    │  (storage/cache.py)        │      │  (ai/*.py)                 │
    │                            │      │                            │
    │  EmailCache                │      │  EmailCategorizer          │
    │  • Store/retrieve emails   │      │  EmailSummarizer           │
    │  • SQLite operations       │      │  EmailSearcher             │
    │  • Full-text search        │      │                            │
    │  • Statistics              │      │  All use AIClient protocol │
    └────────────────────────────┘      └────────────────────────────┘
                    │                                    │
                    │                                    │ Uses
                    │                                    ▼
                    │                    ┌────────────────────────────┐
                    │                    │  AI CLIENT ABSTRACTION     │
                    │                    │  (ai/client.py)            │
                    │                    │                            │
                    │                    │  AIClient (Protocol)       │
                    │                    │  • complete(prompt, ...)   │
                    │                    │                            │
                    │                    │  ClaudeClient              │
                    │                    │  • Anthropic SDK wrapper   │
                    │                    │                            │
                    │                    │  MockAIClient              │
                    │                    │  • Testing without API     │
                    │                    └────────────────────────────┘
                    │
                    │ Uses
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROVIDER LAYER (providers/)                      │
│                                                                     │
│  EmailProvider (Protocol)                                          │
│  • connect(), disconnect()                                         │
│  • fetch_emails(), mark_as_read(), etc.                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │  GmailProvider (COMPOSITION)                               │    │
│  │                                                            │    │
│  │  Composes:                                                 │    │
│  │  • GmailAuthenticator - OAuth2 authentication             │    │
│  │  • GmailMessageParser - Parse API messages                │    │
│  │  • GmailFetcher - Fetch with retry & parallelization      │    │
│  │  • GmailModifier - Mark read, delete, move, etc.          │    │
│  │                                                            │    │
│  │  Each component has SINGLE RESPONSIBILITY                  │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                     │
│  IMAPProvider                                                      │
│  • Similar structure for IMAP                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Design Principles Applied

### 1. Single Responsibility Principle (SRP)
- **CLI**: Only UI concerns (parse args, display results)
- **Container**: Only object creation and lifecycle
- **Service**: Only business logic orchestration
- **GmailAuthenticator**: Only authentication
- **GmailParser**: Only message parsing
- **GmailFetcher**: Only fetching with retry logic
- **GmailModifier**: Only email modification operations

### 2. Separation of Concerns
Clear layer boundaries:
- CLI never creates objects
- CLI never accesses storage directly
- Service layer is the ONLY way to access storage
- AI layer is decoupled from specific provider

### 3. Dependency Injection
- Container creates all objects
- Dependencies are injected, not created internally
- Easy to swap implementations (e.g., MockAIClient for testing)

### 4. Composition Over Inheritance
- `GmailProvider` composes 4 specialized components
- Each component is independently testable
- Can reuse components in different contexts

### 5. Protocol-Based Abstraction
- `AIClient` protocol allows different AI providers
- `EmailProvider` protocol defines common interface
- Type hints enable IDE support without coupling

## Data Flow Example: Categorizing Emails

```
User runs: python main.py categorize-all --limit 100

1. CLI (main.py:categorize_all)
   ├─ Parse arguments: limit=100
   ├─ Create container with config
   └─ Get dependencies:
      ├─ service = container.email_service
      └─ categorizer = container.categorizer

2. Container (services/container.py)
   ├─ Creates EmailCache (lazy)
   ├─ Creates EmailService with cache
   ├─ Creates ClaudeClient with API key
   └─ Creates EmailCategorizer with client

3. Service (services/email_service.py)
   ├─ Validates limit (1-1000)
   ├─ get_uncategorized_count(limit)
   │  └─ cache.get_uncategorized_emails()
   └─ categorize_uncategorized_emails(categorizer, limit)
      ├─ Yields progress updates
      └─ For each email:
         ├─ categorizer.categorize(email)
         └─ cache.update_category(id, category, reasoning)

4. AI Layer (ai/categorizer.py)
   ├─ _prepare_body(email) - Pure function
   ├─ _build_categorization_prompt(email, body) - Pure function
   ├─ ai_client.complete(prompt) - I/O operation
   └─ _parse_categorization_response(text) - Pure function

5. AI Client (ai/client.py)
   └─ ClaudeClient.complete()
      └─ Anthropic SDK API call

6. Storage (storage/cache.py)
   └─ update_category()
      └─ SQLite UPDATE query

7. CLI displays progress and summary
```

## Testing Strategy

### Unit Tests (Easy with new architecture)

```python
# Test service layer with mock cache
def test_get_emails_validates_limit():
    mock_cache = MockCache()
    service = EmailService(mock_cache)
    
    with pytest.raises(ValueError):
        service.get_emails(limit=-1)  # Invalid limit

# Test AI logic without API calls
def test_categorizer_builds_correct_prompt():
    mock_client = MockAIClient()
    categorizer = EmailCategorizer(mock_client)
    
    prompt = categorizer._build_categorization_prompt(test_email, "body")
    assert "urgent" in prompt
    assert "important" in prompt

# Test Gmail components independently
def test_parser_extracts_subject():
    parser = GmailMessageParser()
    email = parser.parse(gmail_api_message)
    assert email.subject == "Test Subject"
```

### Integration Tests

```python
# Test with real database but mock AI
def test_categorize_stores_in_db():
    cache = EmailCache(":memory:")  # In-memory SQLite
    mock_client = MockAIClient(responses={
        "categorize": "Category: urgent\nReasoning: Test"
    })
    categorizer = EmailCategorizer(mock_client)
    service = EmailService(cache)
    
    # Store test email
    cache.store_email(test_email, "gmail")
    
    # Categorize
    list(service.categorize_uncategorized_emails(categorizer, limit=1))
    
    # Verify
    emails = cache.get_emails(limit=1)
    assert emails[0]['category'] == 'urgent'
```

## File Organization

```
AI-email-management-tool/
├── main.py                    # CLI entry point
├── config.py                  # Configuration management
├── services/
│   ├── container.py          # Dependency injection
│   └── email_service.py      # Business logic
├── providers/
│   ├── base.py               # Email dataclass + protocol
│   ├── gmail.py              # Gmail provider (composition)
│   ├── gmail/
│   │   ├── authenticator.py # OAuth2 authentication
│   │   ├── parser.py        # Message parsing
│   │   ├── fetcher.py       # Email fetching
│   │   └── modifier.py      # Email modification
│   └── imap.py              # IMAP provider
├── ai/
│   ├── client.py            # AI client abstraction
│   ├── categorizer.py       # Email categorization
│   ├── summarizer.py        # Email summarization
│   └── search.py            # Natural language search
├── storage/
│   ├── cache.py             # SQLite cache layer
│   └── schema.sql           # Database schema
├── parsers/
│   └── email_parser.py      # Email content parsing
└── utils/
    └── formatting.py        # Display utilities
```

## Benefits of New Architecture

### Maintainability
- **Before**: 756-line GmailProvider class
- **After**: 4 focused classes (~200 lines each)

### Testability
- **Before**: Required API keys to test anything
- **After**: Pure functions + dependency injection = easy testing

### Extensibility
- Want to add OpenAI support? Just implement `AIClient`
- Want to add Outlook provider? Just implement `EmailProvider`
- Want custom caching? Just implement cache interface

### Readability
- Each file has single, clear purpose
- Easy to find relevant code
- Consistent patterns throughout

### Performance
- Same performance characteristics
- Container uses lazy initialization
- Composition has zero overhead
