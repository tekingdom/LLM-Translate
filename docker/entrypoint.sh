#!/bin/sh
set -e

# Inside Docker, localhost is the container — reach host DB via host.docker.internal
if [ -n "$DATABASE_URL" ]; then
  case "$DATABASE_URL" in
    *@localhost:*|*@127.0.0.1:*)
      export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's/@localhost:/@host.docker.internal:/; s/@127.0.0.1:/@host.docker.internal:/')
      echo "DATABASE_URL host remapped for Docker: using host.docker.internal"
      ;;
  esac
fi

echo "Running database migrations..."
python scripts/migrate.py

echo "Starting LLM Translate web service..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
