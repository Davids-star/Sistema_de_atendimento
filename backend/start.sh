#!/usr/bin/env bash
set -e

# Corrige URLs do PostgreSQL do Render (postgres:// -> postgresql+psycopg://)
if [ -n "$DATABASE_URL" ]; then
  export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres://|postgresql+psycopg://|' | sed 's|^postgresql://|postgresql+psycopg://|')
fi

# Executa migrações pendentes no banco de dados automaticamente
echo "Aplicando migrações do banco de dados (Alembic)..."
alembic upgrade head

# Inicia a API FastAPI com o Uvicorn na porta fornecida pelo Render
PORT="${PORT:-8000}"
echo "Iniciando FastAPI na porta $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
