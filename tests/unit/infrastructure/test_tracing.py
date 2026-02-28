"""Unit tests for the @traced decorator and traced_subsegment context manager.

Validates: Requirements 31.3, 31.7
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


async def test_traced_calls_function_normally() -> None:
    """@traced passes through to the wrapped function when X-Ray is unavailable."""
    from src.application.tracing import traced

    call_count = 0

    @traced
    async def my_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    result = await my_func(5)
    assert result == 10
    assert call_count == 1


async def test_traced_propagates_exceptions() -> None:
    """@traced re-raises exceptions from the wrapped function."""
    from src.application.tracing import traced

    @traced
    async def failing_func() -> None:
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await failing_func()


async def test_traced_subsegment_is_noop_without_xray() -> None:
    """traced_subsegment is a no-op when X-Ray is unavailable."""
    from src.application.tracing import traced_subsegment

    entered = False
    with traced_subsegment("test-segment") as seg:
        entered = True
        # seg is None when X-Ray is unavailable — that's the expected fallback
        _ = seg  # suppress unused variable warning

    assert entered  # context manager was entered and exited cleanly


async def test_traced_preserves_function_name() -> None:
    """@traced preserves __name__ and __qualname__ via functools.wraps."""
    from src.application.tracing import traced

    @traced
    async def my_named_function() -> None:
        pass

    assert my_named_function.__name__ == "my_named_function"


async def test_traced_preserves_return_value_with_args() -> None:
    """@traced correctly passes args and kwargs through to the wrapped function."""
    from src.application.tracing import traced

    @traced
    async def add(a: int, b: int = 0) -> int:
        return a + b

    assert await add(3, b=4) == 7


async def test_traced_with_xray_creates_subsegment() -> None:
    """@traced creates a subsegment when X-Ray recorder is available."""
    mock_subsegment = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_subsegment)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    mock_recorder = MagicMock()
    mock_recorder.in_subsegment.return_value = mock_context_manager

    import src.application.tracing as tracing_module

    with (
        patch.object(tracing_module, "_xray_available", True),
        patch.object(tracing_module, "xray_recorder", mock_recorder),
    ):

        @tracing_module.traced
        async def traced_func() -> str:
            return "ok"

        result = await traced_func()

    assert result == "ok"
    mock_recorder.in_subsegment.assert_called_once()
    # Subsegment name should contain the function qualname
    call_args = mock_recorder.in_subsegment.call_args
    assert "traced_func" in call_args[0][0]


async def test_traced_records_exception_on_subsegment() -> None:
    """@traced calls add_exception on the subsegment when the function raises."""
    mock_subsegment = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_subsegment)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    mock_recorder = MagicMock()
    mock_recorder.in_subsegment.return_value = mock_context_manager

    import src.application.tracing as tracing_module

    with (
        patch.object(tracing_module, "_xray_available", True),
        patch.object(tracing_module, "xray_recorder", mock_recorder),
    ):

        @tracing_module.traced
        async def boom() -> None:
            raise RuntimeError("kaboom")

        with pytest.raises(RuntimeError, match="kaboom"):
            await boom()

    mock_subsegment.add_exception.assert_called_once()
    exc_arg = mock_subsegment.add_exception.call_args[0][0]
    assert isinstance(exc_arg, RuntimeError)


async def test_traced_falls_back_when_subsegment_creation_fails() -> None:
    """@traced runs the function without tracing if subsegment creation itself raises."""
    mock_recorder = MagicMock()
    mock_recorder.in_subsegment.side_effect = Exception("xray broken")

    import src.application.tracing as tracing_module

    with (
        patch.object(tracing_module, "_xray_available", True),
        patch.object(tracing_module, "xray_recorder", mock_recorder),
    ):

        @tracing_module.traced
        async def safe_func() -> int:
            return 42

        # Should not raise — falls back to running without tracing
        result = await safe_func()

    assert result == 42


async def test_traced_subsegment_with_xray_yields_subsegment() -> None:
    """traced_subsegment yields the subsegment object when X-Ray is available."""
    mock_subsegment = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_subsegment)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    mock_recorder = MagicMock()
    mock_recorder.in_subsegment.return_value = mock_context_manager

    import src.application.tracing as tracing_module

    with (
        patch.object(tracing_module, "_xray_available", True),
        patch.object(tracing_module, "xray_recorder", mock_recorder),
        tracing_module.traced_subsegment("my-segment") as seg,
    ):
        assert seg is mock_subsegment

    mock_recorder.in_subsegment.assert_called_once_with("my-segment")


async def test_traced_subsegment_falls_back_on_exception() -> None:
    """traced_subsegment yields None and doesn't raise if xray_recorder errors."""
    mock_recorder = MagicMock()
    mock_recorder.in_subsegment.side_effect = Exception("recorder broken")

    import src.application.tracing as tracing_module

    with (
        patch.object(tracing_module, "_xray_available", True),
        patch.object(tracing_module, "xray_recorder", mock_recorder),
        tracing_module.traced_subsegment("broken-segment") as seg,
    ):
        assert seg is None  # graceful fallback
