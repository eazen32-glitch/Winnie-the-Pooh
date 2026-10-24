-- Schema reference only, from an isolated migrated fixture. No data exported.
-- Preserve the real initialize()/_migrate() path; do not reset existing databases.
CREATE TABLE users (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('jobseeker','hr')),
                    onboarding_complete INTEGER NOT NULL DEFAULT 0,
                    resume_json TEXT, profile_version INTEGER NOT NULL DEFAULT 0,
                    demo_key TEXT UNIQUE
                );

CREATE TABLE companies (
                    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                    name TEXT NOT NULL, industry TEXT NOT NULL, location TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
                    synthetic INTEGER NOT NULL DEFAULT 1
                , verification_status TEXT NOT NULL DEFAULT 'unverified', verification_reason TEXT NOT NULL DEFAULT '', registration_number TEXT NOT NULL DEFAULT '', recruiter_identity TEXT NOT NULL DEFAULT '', evidence_note TEXT NOT NULL DEFAULT '', verification_submitted_at TEXT, verification_reviewed_at TEXT, verification_mode TEXT NOT NULL DEFAULT '', verification_evidence_json TEXT NOT NULL DEFAULT '{}', registry_snapshot_json TEXT NOT NULL DEFAULT '{}', domain_snapshot_json TEXT NOT NULL DEFAULT '{}', domain_challenge_json TEXT NOT NULL DEFAULT '{}', verification_review_json TEXT NOT NULL DEFAULT '{}', verification_expires_at TEXT);

CREATE TABLE jobs (
                    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                    title TEXT NOT NULL, role_id TEXT NOT NULL, description TEXT NOT NULL,
                    location TEXT NOT NULL, work_mode TEXT NOT NULL, employment_type TEXT NOT NULL,
                    required_skills_json TEXT NOT NULL, deadline TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
                , salary_min REAL, salary_max REAL, salary_currency TEXT, salary_period TEXT);
