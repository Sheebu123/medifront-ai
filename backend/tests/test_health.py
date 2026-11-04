"""Health endpoint checks using only the Python standard library."""

import json
import unittest
from typing import Any

from app.main import app


async def asgi_get(path: str) -> tuple[int, dict[str, Any]]:
    """Call an ASGI app directly and return the HTTP status and JSON body."""
    messages: list[dict[str, Any]] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"testserver"), (b"accept", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "state": {},
        },
        receive,
        send,
    )

    status = next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status, json.loads(body)


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_endpoint_returns_healthy_status(self) -> None:
        status, body = await asgi_get("/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
