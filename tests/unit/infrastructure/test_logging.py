"""Unit tests for infrastructure logging configuration."""

from unittest.mock import patch

import structlog

from src.infrastructure.logging import configure_logging


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_sets_json_renderer(self) -> None:
        """Verify structlog is configured with JSONRenderer for CloudWatch."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            mock_configure.assert_called_once()
            call_kwargs = mock_configure.call_args[1]
            processors = call_kwargs["processors"]

            # JSONRenderer must be the last processor
            assert isinstance(processors[-1], structlog.processors.JSONRenderer)

    def test_configure_logging_includes_contextvars_processor(self) -> None:
        """Verify merge_contextvars is included for correlation ID propagation."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            call_kwargs = mock_configure.call_args[1]
            processors = call_kwargs["processors"]

            assert structlog.contextvars.merge_contextvars in processors

    def test_configure_logging_includes_timestamper(self) -> None:
        """Verify ISO timestamp processor is included."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            call_kwargs = mock_configure.call_args[1]
            processors = call_kwargs["processors"]

            timestampers = [
                p for p in processors if isinstance(p, structlog.processors.TimeStamper)
            ]
            assert len(timestampers) == 1

    def test_configure_logging_includes_log_level(self) -> None:
        """Verify log level processor is included."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            call_kwargs = mock_configure.call_args[1]
            processors = call_kwargs["processors"]

            assert structlog.stdlib.add_log_level in processors

    def test_configure_logging_uses_bound_logger(self) -> None:
        """Verify BoundLogger wrapper class is used."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            call_kwargs = mock_configure.call_args[1]
            assert call_kwargs["wrapper_class"] is structlog.stdlib.BoundLogger

    def test_configure_logging_default_log_level_is_info(self) -> None:
        """Verify default log_level parameter is INFO."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry")

            # Should not raise — default log_level is "INFO"
            mock_configure.assert_called_once()

    def test_configure_logging_accepts_custom_log_level(self) -> None:
        """Verify custom log_level parameter is accepted."""
        with patch.object(structlog, "configure") as mock_configure:
            configure_logging("ugsys-projects-registry", log_level="DEBUG")

            mock_configure.assert_called_once()
