-- Acestus Local-First SQLite Schema
-- Source of truth for daily work, synced from Linear/Notion/GitHub at start and end of day

-- ============================================================================
-- TICKETS (from Linear)
-- ============================================================================
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,                        -- Linear issue ID (ENG-123)
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL,                       -- pending, in_progress, blocked, waiting_review, done
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    linear_id TEXT UNIQUE NOT NULL,             -- Internal Linear UUID
    linear_url TEXT,
    assignee TEXT,                              -- user ID
    estimate_points INTEGER,                    -- Fibonacci points
    swimlane TEXT,                              -- flow:todo, flow:in_progress, etc.
    priority TEXT,                              -- P0, P1, P2, P3
    tags TEXT,                                  -- JSON array of tag strings
    depends_on TEXT,                            -- Comma-separated ticket IDs
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PULL REQUESTS (from GitHub)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pull_requests (
    id TEXT PRIMARY KEY,                        -- owner/repo#number
    repo TEXT NOT NULL,                         -- full repo path (org/name)
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    state TEXT NOT NULL,                        -- open, closed, merged
    author TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    merged_at TIMESTAMP,
    review_status TEXT,                         -- draft, pending_review, approved, changes_requested
    related_ticket TEXT,                        -- Link to tickets table if applicable
    branch_name TEXT,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- GITHUB ISSUES
-- ============================================================================
CREATE TABLE IF NOT EXISTS github_issues (
    id TEXT PRIMARY KEY,                        -- owner/repo#number
    repo TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    state TEXT NOT NULL,                        -- open, closed
    assignee TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    labels TEXT,                                -- JSON array
    related_ticket TEXT,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- WORK LOGS (daily tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS work_logs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    ticket_id TEXT NOT NULL,
    date TEXT NOT NULL,                         -- YYYY-MM-DD
    duration_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_linear BOOLEAN DEFAULT 0,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

-- ============================================================================
-- COMMENTS TO POST (Linear/Notion)
-- ============================================================================
CREATE TABLE IF NOT EXISTS comments_pending (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    target_type TEXT NOT NULL,                  -- 'linear_ticket', 'notion_page'
    target_id TEXT NOT NULL,                    -- Linear issue ID or Notion page ID
    content TEXT NOT NULL,                      -- Markdown content
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    posted_at TIMESTAMP,
    status TEXT DEFAULT 'pending',              -- pending, posted, failed
    error_message TEXT
);

-- ============================================================================
-- NOTION PAGES TO PUBLISH
-- ============================================================================
CREATE TABLE IF NOT EXISTS pages_pending (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    parent_page_id TEXT,                        -- Parent page in Notion
    title TEXT NOT NULL,
    content TEXT NOT NULL,                      -- Markdown/HTML content
    page_type TEXT,                             -- 'standup', 'crm', 'job_search', 'weekly', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    status TEXT DEFAULT 'pending',              -- pending, published, failed
    error_message TEXT,
    notion_page_id TEXT                         -- After creation
);

-- ============================================================================
-- CRM (Contacts, Companies, Notes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    company_id TEXT,
    title TEXT,                                 -- Job title
    notes TEXT,
    last_contacted TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_notion BOOLEAN DEFAULT 0,
    FOREIGN KEY(company_id) REFERENCES crm_companies(id)
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    industry TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_notion BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crm_interactions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    contact_id TEXT NOT NULL,
    interaction_type TEXT,                      -- email, call, meeting, coffee, etc.
    date TIMESTAMP NOT NULL,
    notes TEXT,
    follow_up_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES crm_contacts(id)
);

-- ============================================================================
-- JOB SEARCH TRACKING
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_search_applications (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    company TEXT NOT NULL,
    position_title TEXT NOT NULL,
    url TEXT,
    status TEXT NOT NULL,                       -- applied, interviewing, offer, rejected, withdrawn
    date_applied TIMESTAMP NOT NULL,
    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    salary_range TEXT,
    recruiter_contact TEXT,
    follow_up_date TIMESTAMP,
    synced_to_notion BOOLEAN DEFAULT 0
);

-- ============================================================================
-- ROUNDS STATE (Kanban lanes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS rounds_state (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    lane_number INTEGER NOT NULL UNIQUE,        -- 1-5 for 5 lanes
    current_ticket_id TEXT,                     -- Active ticket in this lane
    status TEXT DEFAULT 'idle',                 -- idle, active, waiting, blocked
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(current_ticket_id) REFERENCES tickets(id)
);

-- ============================================================================
-- SYNC STATE (Track last sync timestamps)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,                    -- 'linear', 'notion', 'github'
    last_sync_at TIMESTAMP,
    next_sync_at TIMESTAMP,
    status TEXT DEFAULT 'idle',                 -- idle, syncing, success, error
    error_message TEXT,
    synced_count INTEGER DEFAULT 0
);

-- ============================================================================
-- INBOX (Unified capture)
-- ============================================================================
CREATE TABLE IF NOT EXISTS inbox_entries (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    title TEXT NOT NULL,
    notes TEXT,
    source TEXT,                                -- 'manual', 'email', 'pr', 'issue'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    status TEXT DEFAULT 'inbox'                 -- inbox, backlog, in_progress, done
);

-- ============================================================================
-- INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_swimlane ON tickets(swimlane);
CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);
CREATE INDEX IF NOT EXISTS idx_work_logs_ticket_date ON work_logs(ticket_id, date);
CREATE INDEX IF NOT EXISTS idx_comments_pending_status ON comments_pending(status);
CREATE INDEX IF NOT EXISTS idx_pages_pending_status ON pages_pending(status);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_company ON crm_contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_job_search_status ON job_search_applications(status);
CREATE INDEX IF NOT EXISTS idx_rounds_state_lane ON rounds_state(lane_number);
