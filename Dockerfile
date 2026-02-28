# syntax=docker/dockerfile:1
FROM public.ecr.aws/lambda/python:3.13

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first (layer cache)
COPY pyproject.toml uv.lock ./

# Export and install production dependencies only
RUN uv export --no-dev --no-hashes -o requirements.txt && \
    pip install -r requirements.txt -t "${LAMBDA_TASK_ROOT}" --quiet && \
    rm requirements.txt

# Copy application source and Lambda entry point
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
