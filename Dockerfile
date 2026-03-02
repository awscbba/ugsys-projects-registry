# syntax=docker/dockerfile:1
FROM public.ecr.aws/lambda/python:3.13

# Install uv and git (needed for git-sourced dependencies)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN dnf install -y git && dnf clean all

# Copy dependency manifests first (layer cache)
COPY pyproject.toml uv.lock ./

# Install production dependencies directly into LAMBDA_TASK_ROOT (no venv)
RUN UV_PROJECT_ENVIRONMENT="${LAMBDA_TASK_ROOT}" \
    uv sync --frozen --no-dev --no-install-project \
    --python /var/lang/bin/python3.13

# Copy application source and Lambda entry point
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
