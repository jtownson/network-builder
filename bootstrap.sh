#!/usr/bin/env bash
set -e

PROJECT_NAME="network-builder"

echo "🚀 Bootstrapping project: $PROJECT_NAME"

# Root
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# -----------------------------
# Top-level files
# -----------------------------
touch README.md
touch .gitignore
touch .env.example
touch docker-compose.yml

# -----------------------------
# Database
# -----------------------------
mkdir -p db/migrations/versions
touch db/schema.sql
touch db/partitions.sql
touch db/migrations/README.md

# -----------------------------
# Application
# -----------------------------
mkdir -p app/api/routes
mkdir -p app/core
mkdir -p app/models
mkdir -p app/embed

touch app/__init__.py
touch app/api/main.py

touch app/api/__init__.py
touch app/api/routes/messages.py
touch app/api/routes/social_graph.py
touch app/api/routes/orgs.py

touch app/embed/__init__.py

touch app/core/config.py
touch app/core/logging.py
touch app/core/db.py

touch app/models/org.py
touch app/models/user.py
touch app/models/message.py
touch app/models/cluster.py

touch app/services/ingestion.py
touch app/services/graph_query.py
touch app/services/explain.py

# -----------------------------
# Workers
# -----------------------------
mkdir -p workers
touch workers/__init__.py
touch workers/embedder.py
touch workers/clusterer.py
touch workers/aggregator.py

# -----------------------------
# Scripts / tooling
# -----------------------------
mkdir -p scripts
touch scripts/seed_dummy_data.py
touch scripts/create_partitions.py
touch scripts/backfill_embeddings.py
touch scripts/backfill_user_cluster.py

# -----------------------------
# Tests
# -----------------------------
mkdir -p tests
touch tests/test_ingestion.py
touch tests/test_social_graph.py

# -----------------------------
# Ops / deployment
# -----------------------------
mkdir -p nats
