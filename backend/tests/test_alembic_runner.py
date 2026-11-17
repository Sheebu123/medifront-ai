"""Focused tests for Alembic's Windows asyncio loop selection."""

import asyncio
import selectors
import unittest
from unittest.mock import patch

from app.db import alembic_runner


class AlembicRunnerTests(unittest.TestCase):
    def test_windows_selects_selector_event_loop(self) -> None:
        captured = {}

        class FakeRunner:
            def __init__(self, *, loop_factory):
                captured["loop_factory"] = loop_factory

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def run(self, coroutine):
                return "ran"

        coroutine = asyncio.sleep(0)
        try:
            with (
                patch.object(alembic_runner.sys, "platform", "win32"),
                patch.object(alembic_runner.asyncio, "Runner", FakeRunner),
            ):
                result = alembic_runner.run_alembic_async(coroutine)

            self.assertEqual(result, "ran")
            loop = captured["loop_factory"]()
            try:
                self.assertIsInstance(loop, asyncio.SelectorEventLoop)
                self.assertIsInstance(loop._selector, selectors.SelectSelector)
            finally:
                loop.close()
        finally:
            coroutine.close()

    def test_non_windows_keeps_asyncio_run(self) -> None:
        coroutine = asyncio.sleep(0)
        with (
            patch.object(alembic_runner.sys, "platform", "linux"),
            patch.object(alembic_runner.asyncio, "run", return_value="ran") as run,
        ):
            result = alembic_runner.run_alembic_async(coroutine)

        self.assertEqual(result, "ran")
        run.assert_called_once_with(coroutine)
        coroutine.close()


if __name__ == "__main__":
    unittest.main()
