CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================
-- Messages (immutable facts)
-- =========================
CREATE TABLE IF NOT EXISTS messages (
  org_id      TEXT NOT NULL,
  message_id  UUID NOT NULL,
  user_id     TEXT NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  source_type TEXT NOT NULL,
  text        TEXT NOT NULL,
  metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_org_ts
  ON messages (org_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_messages_org_user_ts
  ON messages (org_id, user_id, ts DESC);

CREATE INDEX IF NOT EXISTS brin_messages_ts
  ON messages USING brin (ts);

-- =========================
-- Message Embeddings (derived)
-- =========================
CREATE TABLE IF NOT EXISTS message_embeddings (
  org_id        TEXT NOT NULL,
  message_id    UUID NOT NULL,
  model_version TEXT NOT NULL,
  embedding     VECTOR(768) NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, message_id, model_version)
);

CREATE INDEX IF NOT EXISTS idx_message_embeddings_hnsw
  ON message_embeddings USING hnsw (embedding vector_cosine_ops);

-- =========================
-- Clusters (derived)
-- =========================
CREATE TABLE IF NOT EXISTS clusters (
  org_id             TEXT NOT NULL,
  cluster_id         UUID NOT NULL DEFAULT gen_random_uuid(),
  model_version      TEXT NOT NULL,
  centroid_embedding VECTOR(768) NOT NULL,
  label              TEXT NULL,
  effective_count    BIGINT NOT NULL DEFAULT 0,
  last_activity_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_clusters_org_model
  ON clusters (org_id, model_version);

CREATE INDEX IF NOT EXISTS idx_clusters_centroid_hnsw
  ON clusters USING hnsw (centroid_embedding vector_cosine_ops);

-- =========================
-- Message -> Cluster assignments
-- =========================
CREATE TABLE IF NOT EXISTS message_cluster (
  org_id      TEXT NOT NULL,
  message_id  UUID NOT NULL,
  cluster_id  UUID NOT NULL,
  confidence  REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, message_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_message_cluster_cluster
  ON message_cluster (org_id, cluster_id);

-- =========================
-- User -> Cluster participation
-- =========================
CREATE TABLE IF NOT EXISTS user_cluster (
  org_id              TEXT NOT NULL,
  user_id             TEXT NOT NULL,
  cluster_id          UUID NOT NULL,
  participation_score REAL NOT NULL DEFAULT 0.0,
  message_count       BIGINT NOT NULL DEFAULT 0,
  last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, user_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_user_cluster_user
  ON user_cluster (org_id, user_id);

CREATE INDEX IF NOT EXISTS idx_user_cluster_cluster
  ON user_cluster (org_id, cluster_id);
