# ugsys-projects-registry task runner
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install git hooks (run once after cloning)
install-hooks:
    bash scripts/install-hooks.sh

# Sync dependencies
sync:
    uv sync --extra dev

# Run linter
lint:
    uv tool run ruff check src/ tests/

# Format code
format:
    uv tool run ruff format src/ tests/

# Format check (CI)
format-check:
    uv tool run ruff format --check src/ tests/

# Type check
typecheck:
    uv run mypy src/

# Run unit tests
test:
    uv run pytest tests/unit/ -v --tb=short

# Run integration tests
test-integration:
    uv run pytest tests/integration/ -v --tb=short

# Run all tests with coverage
test-all:
    uv run pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

# Show git diff
diff:
    git diff

# Create a feature branch
branch name:
    git checkout -b feature/{{name}}

# Run dev server locally
dev:
    uv run uvicorn src.main:app --reload --port 8003

# ── Frontend ──────────────────────────────────────────────────────────────────

# Install frontend dependencies
web-install:
    cd web && npm install

# Start frontend dev server
web-dev:
    cd web && npm run dev

# Lint frontend
web-lint:
    cd web && npm run lint

# Type-check frontend
web-typecheck:
    cd web && npm run typecheck

# Build frontend
web-build:
    cd web && npm run build

# Format frontend (write)
web-format:
    cd web && npm run format

# Format check frontend (CI)
web-format-check:
    cd web && npm run format:check

# Run frontend tests (single run, no watch)
web-test:
    cd web && pnpm run test

# Run frontend tests with coverage
web-coverage:
    cd web && npm run test:coverage

# Run npm audit at high severity
web-audit:
    cd web && pnpm audit --audit-level=high
