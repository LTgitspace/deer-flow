"""Tests for the desktop sidecar entry point (app.gateway.desktop_entry)."""

from __future__ import annotations

import socket

from app.gateway.desktop_entry import (
    FRONTEND_PORT_MARKER,
    GATEWAY_PORT_MARKER,
    _free_port,
    _resolve_next_standalone,
    _wait_for_health,
)


def test_free_port_returns_ephemeral_port() -> None:
    port = _free_port()
    assert 0 < port < 65536
    # The port must be bindable (nothing else grabbed it).
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_marker_format_matches_tauri_contract() -> None:
    """The stdout markers must be parseable as ``KEY=value`` lines."""
    assert GATEWAY_PORT_MARKER == "DEERFLOW_PORT="
    assert FRONTEND_PORT_MARKER == "FRONTEND_PORT="
    line = f"{GATEWAY_PORT_MARKER}{12345}"
    key, value = line.split("=", 1)
    assert key == "DEERFLOW_PORT"
    assert int(value) == 12345


def test_wait_for_health_rejects_unreachable() -> None:
    """An unreachable port must time out to False, not hang."""
    port = _free_port()
    # Nothing is listening here, so the poll loop should give up.
    assert not _wait_for_health(f"http://127.0.0.1:{port}", timeout=1.0)


def test_wait_for_health_accepts_healthy() -> None:
    """A server returning 200 on /health must pass."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args) -> None:  # noqa: ANN002
            pass

    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        assert _wait_for_health(f"http://127.0.0.1:{port}", timeout=5.0)
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_resolve_next_standalone_from_source() -> None:
    """From a source checkout, the standalone dir resolves to frontend/.next."""
    # The repo layout is <cwd>/frontend/.next/standalone; whether the build
    # output exists depends on whether `pnpm build` ran. The resolver must
    # return None (not raise) when the output is absent.
    result = _resolve_next_standalone()
    assert result is None or result.name == "standalone"
