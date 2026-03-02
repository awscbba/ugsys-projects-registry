"""Infrastructure tracing — re-exports from application layer.

The tracing utilities live in the application layer to avoid application →
infrastructure import violations.  This module re-exports them so that
infrastructure code (e.g. boto3 patching in main.py) can reference a single
canonical location.
"""

from __future__ import annotations

from src.application.tracing import traced, traced_subsegment

__all__ = ["traced", "traced_subsegment"]
