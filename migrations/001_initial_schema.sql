-- THE GREY DIARY — DATABASE MIGRATIONS
-- Run in Supabase SQL Editor in order

-- ============================================================
-- MIGRATION 001: ENABLE EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- MIGRATION 002: USERS TABLE
-- ============================================================
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE NOT NULL,
    google_id           TEXT UNIQUE NOT NULL,
    display_name        TEXT NOT NULL,
    avatar_style        TEXT DEFAULT 'default',
    plan                TEXT DEFAULT 'free' CHECK (plan IN ('free', 'plus', 'premium')),
    plan_expires_at     TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_plan ON users(plan);

-- ============================================================
-- MIGRATION 003: CAPSULES TABLE
-- ============================================================
CREATE TABLE capsules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (
                        category IN ('Love','Family','Career','Regret','Dreams','Life Change')
                    ),
    mood            TEXT NOT NULL CHECK (
                        mood IN ('Fear','Hope','Love','Regret','Unknown')
                    ),
    reveal_date     TIMESTAMPTZ NOT NULL,
    status          TEXT DEFAULT 'draft' CHECK (
                        status IN ('draft','sealed','revealed')
                    ),
    is_public       BOOLEAN DEFAULT true,
    view_count      INTEGER DEFAULT 0,
    sealed_at       TIMESTAMPTZ,
    revealed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_capsules_user_id ON capsules(user_id);
CREATE INDEX idx_capsules_status ON capsules(status);
CREATE INDEX idx_capsules_reveal_date ON capsules(reveal_date);
CREATE INDEX idx_capsules_category ON capsules(category);
CREATE INDEX idx_capsules_mood ON capsules(mood);
CREATE INDEX idx_capsules_public_revealed ON capsules(status, is_public) 
    WHERE status = 'revealed' AND is_public = true;

-- ============================================================
-- MIGRATION 004: CAPSULE REFLECTIONS (Grey Observer)
-- ============================================================
CREATE TABLE capsule_reflections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capsule_id      UUID UNIQUE NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    reflection      TEXT NOT NULL,
    model_used      TEXT,
    generated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_reflections_capsule_id ON capsule_reflections(capsule_id);

-- ============================================================
-- MIGRATION 005: CAPSULE ECHOES
-- ============================================================
CREATE TABLE capsule_echoes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capsule_id      UUID UNIQUE NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    mood            TEXT CHECK (mood IN ('Fear','Hope','Love','Regret','Unknown','Peace')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_echoes_capsule_id ON capsule_echoes(capsule_id);

-- ============================================================
-- MIGRATION 006: REACTIONS
-- ============================================================
CREATE TABLE reactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capsule_id      UUID NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN ('heart','heartbreak','fire','candle')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(capsule_id, user_id, type)
);

CREATE INDEX idx_reactions_capsule_id ON reactions(capsule_id);
CREATE INDEX idx_reactions_user_id ON reactions(user_id);

-- Aggregated reaction counts view
CREATE VIEW capsule_reaction_counts AS
    SELECT 
        capsule_id,
        COUNT(*) FILTER (WHERE type = 'heart') AS heart,
        COUNT(*) FILTER (WHERE type = 'heartbreak') AS heartbreak,
        COUNT(*) FILTER (WHERE type = 'fire') AS fire,
        COUNT(*) FILTER (WHERE type = 'candle') AS candle
    FROM reactions
    GROUP BY capsule_id;

-- ============================================================
-- MIGRATION 007: COURT SESSIONS
-- ============================================================
CREATE TABLE court_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capsule_id      UUID NOT NULL REFERENCES capsules(id),
    scheduled_for   TIMESTAMPTZ NOT NULL,
    status          TEXT DEFAULT 'pending' CHECK (
                        status IN ('pending','active','archived')
                    ),
    verdict         TEXT,
    verdict_count   JSONB DEFAULT '{"stayed":0,"left":0,"understood":0,"unknown":0}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(scheduled_for::DATE)  -- one court per day
);

CREATE INDEX idx_court_scheduled_for ON court_sessions(scheduled_for);
CREATE INDEX idx_court_status ON court_sessions(status);

-- ============================================================
-- MIGRATION 008: COURT QUESTIONS
-- ============================================================
CREATE TABLE court_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES court_sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    is_answered     BOOLEAN DEFAULT false,
    answer          TEXT,
    upvotes         INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_questions_session_id ON court_questions(session_id);

-- ============================================================
-- MIGRATION 009: COURT VOTES
-- ============================================================
CREATE TABLE court_votes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES court_sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(session_id, user_id)
);

CREATE INDEX idx_votes_session_id ON court_votes(session_id);

-- ============================================================
-- MIGRATION 010: GUARDIAN REPORTS
-- ============================================================
CREATE TABLE guardian_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start      DATE UNIQUE NOT NULL,
    content         TEXT NOT NULL,
    stats           JSONB,
    model_used      TEXT,
    generated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_guardian_week_start ON guardian_reports(week_start DESC);

-- ============================================================
-- MIGRATION 011: PERSONAL REPORTS (Premium)
-- ============================================================
CREATE TABLE personal_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    capsule_count   INTEGER,
    generated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_personal_reports_user_id ON personal_reports(user_id);
CREATE INDEX idx_personal_reports_generated ON personal_reports(user_id, generated_at DESC);

-- ============================================================
-- MIGRATION 012: SUBSCRIPTIONS
-- ============================================================
CREATE TABLE subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan                    TEXT NOT NULL CHECK (plan IN ('plus','premium')),
    provider                TEXT NOT NULL CHECK (provider IN ('razorpay','paypal')),
    provider_sub_id         TEXT UNIQUE,
    provider_order_id       TEXT,
    status                  TEXT DEFAULT 'active' CHECK (
                                status IN ('active','cancelled','expired','pending')
                            ),
    amount                  INTEGER NOT NULL,
    currency                TEXT DEFAULT 'INR',
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- ============================================================
-- MIGRATION 013: PUSH SUBSCRIPTIONS
-- ============================================================
CREATE TABLE push_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, endpoint)
);

-- ============================================================
-- MIGRATION 014: ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Users: can only read/update own profile
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Capsules: own capsules fully, public revealed for all
ALTER TABLE capsules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own capsules" ON capsules
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Anyone reads public revealed" ON capsules
    FOR SELECT USING (status = 'revealed' AND is_public = true);

-- Reactions: own reactions, read all
ALTER TABLE reactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own reactions" ON reactions
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Anyone reads reactions" ON reactions
    FOR SELECT USING (true);

-- ============================================================
-- MIGRATION 015: FUNCTIONS + TRIGGERS
-- ============================================================

-- Auto-reveal capsules when reveal_date passes
CREATE OR REPLACE FUNCTION auto_reveal_capsules()
RETURNS void AS $$
BEGIN
    UPDATE capsules
    SET 
        status = 'revealed',
        revealed_at = now()
    WHERE 
        status = 'sealed' 
        AND reveal_date <= now();
END;
$$ LANGUAGE plpgsql;

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER capsules_updated_at BEFORE UPDATE ON capsules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- MIGRATION 016: SEED DATA (dev only)
-- ============================================================

-- Insert test display names for dev
INSERT INTO users (email, google_id, display_name, plan) VALUES
    ('test@example.com', 'google_test_001', 'Midnight Wanderer', 'free'),
    ('premium@example.com', 'google_test_002', 'Grey Sparrow', 'premium')
ON CONFLICT DO NOTHING;
