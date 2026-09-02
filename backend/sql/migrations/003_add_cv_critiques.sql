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
