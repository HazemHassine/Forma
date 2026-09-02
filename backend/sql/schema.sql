CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    data TEXT NOT NULL,
    template_id TEXT NOT NULL DEFAULT 'modern',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    url TEXT,
    status TEXT DEFAULT 'applied',
    resume_version_id INTEGER,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    updated_at TIMESTAMP,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id)
);

CREATE TABLE IF NOT EXISTS cover_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_version_id INTEGER NOT NULL,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    source_url TEXT,
    job_post TEXT NOT NULL,
    content TEXT NOT NULL,
    generation_context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id)
);

CREATE TABLE IF NOT EXISTS company_research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    website_url TEXT,
    role TEXT,
    job_context TEXT,
    focus TEXT,
    report TEXT NOT NULL,
    researched_at TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_company_research_created
ON company_research_reports (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_company_research_company
ON company_research_reports (company COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS profile_assets (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    data BLOB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cv_critiques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_version_id INTEGER NOT NULL,
    target_role TEXT,
    job_description TEXT,
    provider TEXT NOT NULL DEFAULT 'gemini',
    overall_score INTEGER NOT NULL,
    summary TEXT NOT NULL,
    critique_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_cv_critiques_version
ON cv_critiques (resume_version_id, created_at DESC);

CREATE TABLE IF NOT EXISTS context_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'dump',
    content TEXT NOT NULL,
    url TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_context_sources_active
ON context_sources (is_active, id DESC);

CREATE TABLE IF NOT EXISTS context_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES context_sources(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_context_items_category
ON context_items (category);

CREATE INDEX IF NOT EXISTS idx_context_items_active
ON context_items (is_active, id DESC);

CREATE INDEX IF NOT EXISTS idx_context_items_source
ON context_items (source_id);

CREATE TABLE IF NOT EXISTS context_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    key_differentiators TEXT NOT NULL DEFAULT '[]',
    target_roles TEXT NOT NULL DEFAULT '[]',
    stats TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

