"""AWS Lambda entry point — Mangum wraps the FastAPI ASGI app."""
from mangum import Mangum

from src.main import app  # noqa: E402

handler = Mangum(app, lifespan="on")
