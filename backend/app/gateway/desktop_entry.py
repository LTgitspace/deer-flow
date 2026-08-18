"""Desktop entry point: run the full Gateway as a Tauri sidecar.

Spawns the FastAPI Gateway (with the embedded LangGraph runtime) on an
ephemeral port, prints the resolved ports to stdout for the parent Tauri
process, and manages the Next.js standalone child server.

Lifecycle contract with the Tauri shell (``desktop/src-tauri/src/main.rs``):

- stdout is machine-readable: two lines are emitted once the services are up:

      DEERFLOW_PORT=<port>
      FRONTEND_PORT=<port>

  The Tauri process reads these to point the webview at
  ``http://127.0.0.1:<FRONTEND_PORT>`` and the API bridge at the gateway.
- stderr carries human-readable logs (the Gateway's logging config already
  auto-disables ANSI colors when stderr is not a TTY).
- SIGINT / SIGTERM trigger graceful shutdown: the Next child is terminated
  first, then uvicorn's shutdown hooks (subagent executor, memory flush,
  checkpoint writer) run with the Gateway's bounded shutdown timeouts.

Desktop mode environment (set before this process starts, or by the Tauri
shell when spawning the sidecar):

- ``DEER_FLOW_AUTH_DISABLED=1``: run as the synthetic local admin, no login.
- ``UNI_DEER_HOME``: runtime state (defaults to ``~/.deer-flow``).
- ``DEER_FLOW_INTERNAL_GATEWAY_BASE_URL``: set by this entry to the resolved
  gateway port so the Next.js rewrites proxy ``/api/*`` correctly.

Usage::

    python -m app.gateway.desktop_entry            # normal run
    python -m app.gateway.desktop_entry --smoke-test  # CI packaging smoke test
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

#: Marker lines printed to stdout for the Tauri shell to parse.
GATEWAY_PORT_MARKER = "DEERFLOW_PORT="
FRONTEND_PORT_MARKER = "FRONTEND_PORT="

#: Where the Next.js standalone server is expected relative to the repo root
#: when running from source, or to the sidecar bundle root when frozen.
_NEXT_STANDALONE_DIR = Path("frontend") / ".next" / "standalone"

_SMOKE_TIMEOUT_SECONDS = 90.0


def _free_port() -> int:
    """Return an available ephemeral port (bind port 0, then close)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_next_standalone() -> Path | None:
    """Locate the Next.js standalone server directory.

    From source: ``<repo>/frontend/.next/standalone``.
    Frozen (PyInstaller): the standalone output is shipped next to the
    sidecar binary as ``desktop/dist`` and copied to ``frontend/.next/
    standalone`` at build time; fall back to the repo layout.
    """
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates = (
            bundle_root / "frontend" / ".next" / "standalone",
            Path(sys.executable).parent / "frontend" / ".next" / "standalone",
        )
        for candidate in candidates:
            if (candidate / "server.js").exists():
                return candidate
        return None
    candidate = Path.cwd() / _NEXT_STANDALONE_DIR
    return candidate if (candidate / "server.js").exists() else None


async def _spawn_next_standalone(port: int, gateway_port: int) -> subprocess.Popen | None:
    """Spawn the Next.js standalone server on *port*, proxying to the gateway.

    Returns the child handle, or None when the standalone output is not
    present (server-only desktop run).
    """
    standalone = _resolve_next_standalone()
    if standalone is None:
        logger.warning("Next.js standalone output not found; skipping frontend child")
        return None

    env = dict(os.environ)
    env["PORT"] = str(port)
    env["HOSTNAME"] = "127.0.0.1"
    env["DEER_FLOW_INTERNAL_GATEWAY_BASE_URL"] = f"http://127.0.0.1:{gateway_port}"
    # The standalone server resolves its static assets relative to the
    # bundle; run it with the standalone dir as cwd so .next/static resolves.
    server_js = standalone / "server.js"
    cmd = [sys.executable if not (standalone / "node_modules").exists() else "node", str(server_js)]
    # Prefer the bundled node binary if present (PyInstaller ships it next to
    # the sidecar); otherwise rely on PATH or the Python fallback above.
    bundled_node = Path(sys.executable).parent / "node" if getattr(sys, "frozen", False) else None
    if bundled_node is not None and bundled_node.exists():
        cmd[0] = str(bundled_node)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(standalone),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=None,
            start_new_session=True,
        )
    except OSError as exc:
        logger.error("Failed to spawn Next.js standalone: %s", exc)
        return None
    return proc


def _wait_for_health(base_url: str, timeout: float = _SMOKE_TIMEOUT_SECONDS) -> bool:
    """Poll ``/health`` until it returns 200 or the timeout elapses."""
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _run_uvicorn(gateway_port: int) -> None:
    """Boot the full Gateway app on *gateway_port* (blocking)."""
    import uvicorn

    # The module-level `app = create_app()` in app.gateway.app is the same
    # object uvicorn's string target resolves; reuse the string form so the
    # app factory (and its lifespan) runs exactly as in `make gateway`.
    uvicorn.run(
        "app.gateway.app:app",
        host="127.0.0.1",
        port=gateway_port,
        log_level="info",
    )


def _smoke_test() -> int:
    """Start the gateway on an ephemeral port, verify health, then exit."""
    gateway_port = _free_port()
    base_url = f"http://127.0.0.1:{gateway_port}"
    print(f"{GATEWAY_PORT_MARKER}{gateway_port}", flush=True)

    # In the frozen (PyInstaller) bundle, sys.executable is the sidecar exe
    # itself and does not support `-m`; re-exec it directly with the gateway
    # port. From source, use the module form.
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--gateway-port", str(gateway_port)]
    else:
        cmd = [sys.executable, "-m", "app.gateway.desktop_entry", "--gateway-port", str(gateway_port)]

    env = dict(os.environ)
    env.setdefault("DEER_FLOW_AUTH_DISABLED", "1")
    env.setdefault("DEER_FLOW_HOME", str(Path.home() / ".deer-flow"))

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        print(f"SMOKE FAILED: could not start sidecar: {exc}")
        return 1

    ok = _wait_for_health(base_url)
    if not ok:
        print("SMOKE FAILED: /health did not return 200 within timeout")
        proc.terminate()
        proc.wait(timeout=10)
        return 1

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("SMOKE OK")
    return 0


def _bootstrap_desktop_config(path: Path) -> None:
    """Write a minimal desktop config.yaml on first run.

    The desktop bundle has no source tree to copy ``config.example.yaml``
    from, so a minimal config is generated instead: local sandbox, auth
    disabled, and defaults for the rest. Existing configs are never
    overwritten UNLESS they reference environment variables that are not
    set (the config loader fails hard on missing ``$VAR`` references); in
    that case the config is regenerated so the desktop app always boots.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            content = path.read_text(encoding="utf-8")
            if not _config_has_unset_env_refs(content):
                return  # valid existing config; leave it alone
            logger.warning("Desktop config references unset env vars; regenerating minimal config")
        except OSError:
            pass

    minimal: dict = {
        "config_version": 1,
        "sandbox": {
            "use": "deerflow.sandbox.local:LocalSandboxProvider",
            "allow_host_bash": False,
        },
    }
    # Only reference an env-var model when the key is actually set: the config
    # loader fails hard on missing $VAR references (AppConfig.resolve_env_variables),
    # and the desktop app must boot on first run without a key configured. The
    # user picks a model in Settings afterwards.
    if os.environ.get("OPENAI_API_KEY"):
        minimal["models"] = [
            {
                "name": "default",
                "display_name": "Default model",
                "use": "langchain_openai:ChatOpenAI",
                "model": "gpt-4o",
                "api_key": "$OPENAI_API_KEY",
            }
        ]
    try:
        import yaml

        path.write_text(yaml.safe_dump(minimal, sort_keys=False), encoding="utf-8")
        logger.info("Wrote minimal desktop config to %s", path)
    except Exception:
        logger.warning("Could not bootstrap desktop config at %s", path, exc_info=True)


def _config_has_unset_env_refs(content: str) -> bool:
    """True when the config references a ``$VAR`` whose env var is unset."""
    import re

    for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", content):
        if os.environ.get(match.group(1)) is None:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeerFlow desktop sidecar")
    parser.add_argument("--smoke-test", action="store_true", help="run packaging smoke test and exit")
    parser.add_argument("--gateway-port", type=int, default=0, help="explicit gateway port (0 = ephemeral)")
    parser.add_argument("--frontend-port", type=int, default=0, help="explicit frontend port (0 = ephemeral)")
    parser.add_argument("--skip-frontend", action="store_true", help="do not spawn the Next.js child")
    args = parser.parse_args(argv)

    if args.smoke_test:
        return _smoke_test()

    # Desktop defaults: auth-disabled local admin, runtime state under home.
    os.environ.setdefault("DEER_FLOW_AUTH_DISABLED", "1")
    home = os.environ.get("DEER_FLOW_HOME") or os.environ.get("UNI_DEER_HOME") or str(
        Path.home() / ".deer-flow"
    )
    # The harness Paths.base_dir resolution reads DEER_FLOW_HOME (UNI_DEER_HOME
    # is the documented alias but is not read by paths.py). Set the real one
    # so runtime state (db, memory, uploads) lands under the desktop home.
    os.environ.setdefault("DEER_FLOW_HOME", home)
    os.environ.setdefault("UNI_DEER_HOME", home)

    # Point the config loader at the desktop config. The Gateway's
    # AppConfig.resolve_config_path honours DEER_FLOW_CONFIG_PATH before the
    # source-tree locations; in the frozen desktop bundle there is no source
    # tree, so this env var is the only reliable path.
    desktop_config = Path(home) / "config.yaml"
    os.environ.setdefault("DEER_FLOW_CONFIG_PATH", str(desktop_config))
    if not desktop_config.exists():
        _bootstrap_desktop_config(desktop_config)

    gateway_port = args.gateway_port or _free_port()
    frontend_port = args.frontend_port or _free_port()
    os.environ["DEER_FLOW_INTERNAL_GATEWAY_BASE_URL"] = f"http://127.0.0.1:{gateway_port}"

    # The Next child must start before the gateway so both ports are known
    # when the Tauri shell reads stdout; the child's rewrites point at the
    # gateway port (which is bound momentarily).
    next_proc = None if args.skip_frontend else asyncio.run(_spawn_next_standalone(frontend_port, gateway_port))

    print(f"{GATEWAY_PORT_MARKER}{gateway_port}", flush=True)
    if next_proc is not None:
        print(f"{FRONTEND_PORT_MARKER}{frontend_port}", flush=True)

    def _shutdown(_signum, _frame) -> None:
        logger.info("Shutdown signal received; terminating Next.js child")
        if next_proc is not None:
            next_proc.terminate()
            try:
                next_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                next_proc.kill()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        _run_uvicorn(gateway_port)
    finally:
        if next_proc is not None and next_proc.poll() is None:
            next_proc.terminate()
            try:
                next_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                next_proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
