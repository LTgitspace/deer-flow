# DeerFlow Desktop Application Packaging Plan (Tauri v2 + Python Sidecar)

> **Revision note (verified against this repo):** the original draft assumed a Vite SPA build. This codebase's frontend is **Next.js 16 (App Router)** — there is no Vite. This revision replaces the Vite assumption with the Next.js reality (standalone server + env-based rewrites), pins the desktop auth model (`DEER_FLOW_AUTH_DISABLED`), and requires the sidecar to boot the full Gateway.

Transform DeerFlow into a standalone, lightweight, cross-platform native desktop application for Windows, macOS, and Linux using **Tauri v2** and an **isolated Python Sidecar runtime**.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       NATIVE DESKTOP SHELL (Tauri v2)                       │
│                                                                             │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │     Frontend UI (OS Webview)    │   │    Backend Sidecar (Process)    │  │
│  │   React 19 + Tailwind CSS 4     │   │   FastAPI + deerflow-harness    │  │
│  │   Streamdown, CodeMirror, Icons │   │   (Compiled via PyInstaller)    │  │
│  └────────────────┬────────────────┘   └────────────────┬────────────────┘  │
│                   │                                     │                   │
│                   │◄──────── Localhost HTTP / SSE ──────┤                   │
│                   │          (Dynamic Ephemeral Port)   │                   │
│                   ▼                                     ▼                   │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │   Tauri Native OS Window APIs   │   │  Embedded SQLite & Local Files  │  │
│  │   Frameless Drag, Tray, Hotkeys │   │  ~/.deer-flow/desktop.db        │  │
│  └─────────────────────────────────┘   └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. User Review Required

> [!IMPORTANT]
> **Zero-Server Desktop Model**:
> In desktop mode, **Nginx and Docker are eliminated completely**. 
> - The frontend talks directly to the backend over a local ephemeral port (`http://127.0.0.1:<PORT>`).
> - The execution engine defaults to `deerflow.sandbox.local:LocalSandboxProvider`, running commands in an isolated user workspace (`~/.deer-flow/workspace`) without requiring Docker.
> - **The full Gateway still boots**: the sidecar runs the entire FastAPI app + embedded LangGraph runtime. Auth runs in **auth-disabled mode** (`DEER_FLOW_AUTH_DISABLED=1`) — the repo already supports this: auth is bypassed, requests run as a synthetic local admin user, and CSRF is skipped. Desktop is single-user localhost, so this is intentional and safe, but it must be explicit.
> - **Nginx's role is replaced by Next.js's own rewrites**: the webview loads the Next.js standalone server, which proxies `/api/*` to the FastAPI ephemeral port via the existing env-based `next.config.js` rewrites (`DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`) — no new proxy code needed.

> [!TIP]
> **Performance Targets**:
> - Installer size: **~60–90 MB** (compared to Electron's 180MB+). Note: bundling the Next.js standalone server adds a Node runtime (~40 MB) on top of the Python sidecar; plan for **~100–130 MB** total.
> - Idle RAM usage: **~100–140 MB**.
> - Launch time: **< 400ms**.

---

## 3. Open Questions

1. **Packaging Python**: Do you prefer **PyInstaller standalone binary** (single executable per platform) or an **Astral `uv`-bundled hermetic Python 3.12 folder**?
   *(Recommendation: PyInstaller for single-file cleaner installers; `uv` for faster iterative dev builds).*
2. **Auto-Updater**: Should we configure the Tauri built-in cryptographic auto-updater pointing to GitHub Releases in Phase 1?
3. **Frontend runtime strategy (RESOLVED — Option A)**: bundle the real **Next.js 16 standalone server** (`output: 'standalone'`) inside the sidecar. It reuses 100% of the existing UI, keeps the App Router/server components working, and replaces nginx with Next's own env-based rewrites. *Alternative (rejected for Phase 1): a separate thin SPA client would discard most of the existing Next.js UI and must be rebuilt against the FastAPI/SSE API.*
4. **PyInstaller risk (flagged)**: the harness pulls in LangGraph, SQLAlchemy, uvicorn, 60+ middleware modules, and `skills/public/` data files. Hidden imports and data files must be enumerated in the spec, and the sidecar smoke test must run in CI to catch packaging regressions.

---

## 4. Proposed Changes by Component

```
deer-flow/
├── backend/
│   ├── app/gateway/desktop_entry.py         # [NEW] Ephemeral port desktop runner & lifecycle handler
│   └── desktop_build.spec                   # [NEW] PyInstaller bundle spec for backend
├── frontend/
│   ├── src/components/desktop/
│   │   └── titlebar.tsx                     # [NEW] Frameless native window header bar
│   ├── src/core/api/desktop-bridge.ts       # [NEW] Dynamic backend port resolution for desktop
│   └── next.desktop.config.ts               # [NEW] Desktop build variant: `output: 'standalone'` + env-based gateway rewrites (replaces vite.desktop.config.ts)
├── desktop/                                 # [NEW] Tauri v2 desktop project root
│   ├── package.json
│   └── src-tauri/
│       ├── Cargo.toml                       # [NEW] Rust dependencies (tauri, tauri-plugin-shell)
│       ├── tauri.conf.json                  # [NEW] Window framing, sidecar definitions, permissions
│       ├── build.rs                         # [NEW] Sidecar binary copy hooks
│       └── src/
│           └── main.rs                      # [NEW] Rust lifecycle manager (spawns/kills Python sidecar)
└── scripts/
    └── build_desktop.py                     # [NEW] Cross-platform build & packaging automation script
```

---

### Component 1: Backend Desktop Entry & Packaging

#### [NEW] [desktop_entry.py](file:///c:/github/deer-flow/backend/app/gateway/desktop_entry.py)
* Creates an entry point for desktop invocation.
* **Boots the full Gateway app** (FastAPI + embedded LangGraph runtime) with `DEER_FLOW_AUTH_DISABLED=1` so the desktop session runs as the local synthetic admin without login.
* **Spawns the Next.js standalone server** (from `frontend/.next/standalone`) as a child process on a second ephemeral port.
* Binds to an available ephemeral port (`port=0`), prints `DEERFLOW_PORT=<port>` **and** `FRONTEND_PORT=<port>` to `stdout` for the parent Tauri process to read; sets `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:<gateway-port>` for the Next rewrites.
* Sets default config path to `~/.deer-flow/config.yaml`, runtime state to `~/.deer-flow/`, and SQLite DB to `~/.deer-flow/data.db` (`UNI_DEER_HOME`).
* Intercepts `SIGINT` / `SIGTERM` / `WM_CLOSE` to ensure all spawned subagent processes, the Next child, and locks exit cleanly.

#### [NEW] [desktop_build.spec](file:///c:/github/deer-flow/backend/desktop_build.spec)
* PyInstaller specification bundling:
  * `deerflow` harness package
  * `app.gateway` and `uvicorn`
  * Default `skills/public/` directory (as data files)
  * SQLite / SQLAlchemy drivers
  * Explicit hidden imports for LangGraph, the middleware package (`deerflow.agents.middlewares.*`), and the subagent executor (thread-pool + asyncio) — PyInstaller cannot discover these dynamically
* The Next.js standalone output is **not** PyInstaller-bundled; it ships as `desktop/dist/` next to the sidecar binary.

> **Build note:** `next.config.js` already supports standalone output via the
> `NEXT_CONFIG_BUILD_OUTPUT=standalone` env var — no new `next.desktop.config.ts`
> is needed. The desktop build sets that env var during `pnpm build` and copies
> `frontend/.next/standalone` to `desktop/dist/`.

---

### Component 2: Frontend Desktop Bridge & Titlebar

#### [NEW] [titlebar.tsx](file:///c:/github/deer-flow/frontend/src/components/desktop/titlebar.tsx)
* Custom frameless header bar matching OS dark/light theme.
* Uses `data-tauri-drag-region` for 120Hz native hardware window dragging.
* Houses native minimize, maximize, and close window controls using `@tauri-apps/api/window`.

#### [NEW] [desktop-bridge.ts](file:///c:/github/deer-flow/frontend/src/core/api/desktop-bridge.ts)
* Checks for `window.__TAURI__` environment.
* Reads dynamically assigned backend port from Tauri invoke handler rather than static `http://localhost:8001`.
* In desktop mode the webview loads the Next.js standalone server; the existing `next.config.js` rewrites (keyed off `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`, already read at runtime) proxy `/api/*` to the FastAPI ephemeral port — the bridge only needs to surface the frontend port.

#### [NEW] [next.desktop.config.ts](file:///c:/github/deer-flow/frontend/next.desktop.config.ts)
* Desktop build variant of the existing Next.js 16 config (NOT Vite — the frontend is Next.js App Router and cannot be built as a Vite SPA).
* **Superseded at implementation time**: `next.config.js` already reads `NEXT_CONFIG_BUILD_OUTPUT=standalone` (verified), so the desktop build reuses the existing config with that env var instead of a new file. The desktop shell only adds `titlebar.tsx` and `desktop-bridge.ts`; 100% of `src/app/`, `src/components/`, `src/core/`, and the Tailwind 4 design system are reused.

---

### Component 3: Tauri v2 Native Shell

#### [NEW] [tauri.conf.json](file:///c:/github/deer-flow/desktop/src-tauri/tauri.conf.json)
* **Window Config**: Frameless (`decorations: false`), `transparent: false`, `minWidth: 900`, `minHeight: 650`.
* **Sidecar Definition**: Declares `deerflow-backend` as an external binary.
* **Security & Permissions**: Enables `shell:allow-execute`, `dialog:allow-open`, `fs:allow-read`.

#### [NEW] [main.rs](file:///c:/github/deer-flow/desktop/src-tauri/src/main.rs)
* **Child Process Management**: Spawns `deerflow-backend` on startup.
* Reads the backend port from the sidecar `stdout` stream and passes it to the frontend webview.
* Listens to Tauri window close events and forcefully terminates the child backend process (guaranteeing zero zombie processes).
* *(Optional)* Registers global hotkey (`Alt+Space`) and system tray icon.

---

### Component 4: Build Automation

#### [NEW] [build_desktop.py](file:///c:/github/deer-flow/scripts/build_desktop.py)
A one-command multi-stage build script:
1. `python -m PyInstaller backend/desktop_build.spec` -> outputs sidecar binary to `desktop/src-tauri/binaries/`.
2. `cd frontend && pnpm build:desktop` -> `next build` with `next.desktop.config.ts` (standalone output) -> copy `.next/standalone` to `desktop/dist/`.
3. `cd desktop && cargo tauri build` -> outputs native installer (`.msi`/`.exe` for Windows, `.dmg` for macOS, `.deb` for Linux).

---

## 5. Verification Plan

### Automated Tests
1. **Sidecar Smoke Test**:
   ```bash
   python backend/app/gateway/desktop_entry.py --smoke-test
   ```
   * Asserts backend starts, reports valid port, responds to `/health`, and exits on signal.
   * Asserts the Next.js standalone child starts (when built), reports `FRONTEND_PORT`, and serves the webview index.
2. **Tauri Build & Compilation**:
   ```bash
   python scripts/build_desktop.py --dry-run
   ```

### Manual Verification
1. **Installer Validation**:
   * Install generated `.msi` / `.exe` on a fresh machine without Python, Node, or Docker installed.
2. **End-to-End Chat & Tools**:
   * Send messages, stream responses with animated markdown.
   * Run local bash tool commands (e.g. `ls`, `mkdir`, `python script.py`) in `LocalSandboxProvider`.
   * Open artifacts panel, test CodeMirror editor and file saves.
3. **Graceful Shutdown & Process Isolation**:
   * Close the desktop window -> Open Windows Task Manager / Activity Monitor -> Verify no lingering `deerflow-backend`, `next-server`, or `python` orphan processes.
