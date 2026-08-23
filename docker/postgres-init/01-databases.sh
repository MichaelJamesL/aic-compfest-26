#!/bin/bash
set -eu

# The official image runs this once after POSTGRES_DB exists. The existence
# check also makes manual reruns safe against an already populated volume.
app_database="${APP_DATABASE:-app}"
ai_database="${AI_DATABASE:-ai}"

create_database() {
  database="$1"
  if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
      -tAc "SELECT 1 FROM pg_database WHERE datname = '$database'" | grep -q 1; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
      -c "CREATE DATABASE \"$database\""
  fi
}

create_database "$app_database"
create_database "$ai_database"

for database in "$POSTGRES_DB" "$app_database" "$ai_database"; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" \
    -c 'CREATE EXTENSION IF NOT EXISTS vector'
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$ai_database" <<'SQL'
CREATE TABLE IF NOT EXISTS doc_chunk (
  id BIGSERIAL PRIMARY KEY,
  factory_id TEXT,
  asset_id TEXT,
  doc_id TEXT,
  doc_title TEXT,
  kind TEXT,
  chunk_index INT,
  text TEXT,
  embedding VECTOR(1024)
);
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS factory_id TEXT;
CREATE INDEX IF NOT EXISTS doc_chunk_embedding_idx
  ON doc_chunk USING hnsw (embedding vector_cosine_ops);
SQL
