"""Structured logging configuration for ugsys-projects-registry.

Uses structlog with JSON output for CloudWatch compatibility.
Must be called as the first thing in src/main.py before any other imports.
"""

import structlog


def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure structlog with JSON processors for CloudWatch-ready output.

    Args:
        service_name: The service identifier (e.g. "ugsys-projects-registry").
        log_level: Logging level string. Defaults to "INFO".
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
