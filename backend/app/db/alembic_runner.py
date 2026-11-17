"""Platform-specific asyncio runner for Alembic's async migrations."""

import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any


def _windows_selector_loop() -> asyncio.SelectorEventLoop:
    """Create the selector loop required by psycopg's async driver on Windows."""
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def run_alembic_async(coroutine: Coroutine[Any, Any, Any]) -> Any:
    """Run an Alembic coroutine with psycopg-compatible Windows I/O handling.

    FastAPI's event loop is configured independently. Unix platforms keep the
    standard ``asyncio.run`` behavior used by Alembic before this helper.
    """
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=_windows_selector_loop) as runner:
            return runner.run(coroutine)
    return asyncio.run(coroutine)
