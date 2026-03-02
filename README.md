# ugsys-projects-registry

Project catalog and volunteer subscription management service for the ugsys platform.

## Structure

```
api/    — Backend API (Python, FastAPI, DynamoDB)
web/    — Public frontend (Astro + React, pending)
infra/  — CDK infrastructure stacks (pending)
```

## Setup

```bash
cd api
devbox shell
just sync
just install-hooks
```

## Development

```bash
cd api
just test        # Run unit tests
just lint        # Run linter
just format      # Format code
just typecheck   # Type check
just dev         # Run dev server on port 8003
```
