-- Database schema for email caching

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT,
    html_body TEXT,
    received_date TIMESTAMP NOT NULL,
    fetched_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    has_attachments BOOLEAN DEFAULT 0,
    is_read BOOLEAN DEFAULT 0,
    provider TEXT NOT NULL,

    -- AI-generated fields
    category TEXT,
    category_reasoning TEXT,
    summary TEXT,
    action_items TEXT,

    -- Content analysis fields (AI-generated)
    content_type TEXT,           -- receipt, shipping, promotional, newsletter, etc.
    importance TEXT,             -- high, medium, low
    contains_receipt BOOLEAN DEFAULT 0,
    contains_tracking BOOLEAN DEFAULT 0,
    requires_action BOOLEAN DEFAULT 0,
    is_promotional BOOLEAN DEFAULT 0,
    ai_analyzed BOOLEAN DEFAULT 0,
    ai_analyzed_date TIMESTAMP,

    -- Metadata
    labels TEXT,  -- JSON array stored as text

    UNIQUE(id, provider)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_received_date ON emails(received_date DESC);
CREATE INDEX IF NOT EXISTS idx_sender ON emails(sender);
CREATE INDEX IF NOT EXISTS idx_category ON emails(category);
CREATE INDEX IF NOT EXISTS idx_is_read ON emails(is_read);
CREATE INDEX IF NOT EXISTS idx_provider ON emails(provider);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
    subject,
    sender,
    body,
    content=emails,
    content_rowid=rowid
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
    INSERT INTO emails_fts(rowid, subject, sender, body)
    VALUES (new.rowid, new.subject, new.sender, new.body);
END;

CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
    UPDATE emails_fts
    SET subject = new.subject, sender = new.sender, body = new.body
    WHERE rowid = new.rowid;
END;

CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
    DELETE FROM emails_fts WHERE rowid = old.rowid;
END;

-- Table for storing search history and analytics
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    results_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp DESC);
