# syntax=docker/dockerfile:1
FROM public.ecr.aws/lambda/python:3.13

# Install uv and git (needed for git-sourced dependencies)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN dnf install -y git && dnf clean all

# Copy dependency manifests first (layer cache)
COPY pyproject.toml uv.lock ./

# Export lockfile to requirements.txt, then pip install flat into LAMBDA_TASK_ROOT
RUN uv export --frozen --no-dev --no-hashes --no-emit-project \
        -o /tmp/requirements.txt \
    && pip install \
        --target "${LAMBDA_TASK_ROOT}" \
        --requirement /tmp/requirements.txt \
        --quiet \
    && rm /tmp/requirements.txt

# Copy application source and Lambda entry point
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
