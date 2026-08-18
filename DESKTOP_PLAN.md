# UniDeer Desktop App — Progress & Continuation Plan

> Status snapshot: 2026-08-18. This document records what is done, what is
> verified, what remains, and the exact commands to continue from here.

---

## 1. Goal

Ship a native Windows/macOS/Linux desktop app for UniDeer:

- **Tauri v2** Rust shell (native window, sidecar lifecycle, auto-updater)
- **Python sidecar** (PyInstaller bundle) running the full FastAPI Gateway +
  embedded LangGraph runtime
- **Next.js standalone server** as the webview content (replaces nginx)
- Zero-server model: `DEER_FLOW_AUTH_DISABLED=1`, `LocalSandboxProvider`,
  runtime state under `~/.deer-flow/`

---

## 2. What is DONE (verified working)

### 2.1 Toolchain installed on this machine (Option B: GNU/MinGW)

| Tool | Version | Path |
| --- | --- | --- |
| rustup | 1.29.0 | `~/.cargo/bin` |
| Rust stable-gnu | 1.97.1 (`x86_64-pc-windows-gnu`, **default**) | `~/.rustup` |
| MSYS2 | 2026-06-11 | `C:/msys64` |
| MinGW-w64 GCC | 16.2.0 (`x86_64-w64-mingw32-gcc`) | `C:/msys64/mingw64/bin` |
| Node + npm | 22+ | existing |
| PyInstaller | 6.22.2 | via `uv sync --extra desktop` |

**Important**: every Rust/cargo command needs the GNU toolchain on PATH:

```bash
export PATH="$USERPROFILE/.cargo/bin:/c/msys64/mingw64/bin:$PATH"
```

### 2.2 Backend sidecar (fully working)

- `backend/app/gateway/desktop_entry.py` — desktop entry: boots the full
  Gateway (uvicorn `app.gateway.app:app`), ephemeral port, prints
  `DEERFLOW_PORT=` / `FRONTEND_PORT=` markers, SIGINT/SIGTERM handling,
  `--smoke-test` flag.
- Desktop env defaults: `DEER_FLOW_AUTH_DISABLED=1`, `DEER_FLOW_HOME`
  (`UNI_DEER_HOME` is a docs alias the code does NOT read — the harness reads
  `DEER_FLOW_HOME`), `DEER_FLOW_CONFIG_PATH=~/.deer-flow/config.yaml`.
- First-run config bootstrap: writes a minimal config (local sandbox, no
  model) and **regenerates it if the existing config references unset `$VAR`s**
  (the loader fails hard on missing env vars).
- `backend/desktop_build.spec` — PyInstaller spec (hidden imports for
  `app.*`, middleware package, deermem backends, persistence, community tools;
  data for `skills/public/`, Alembic `migrations/`, memory `backends/` dir).
- `backend/tests/test_desktop_entry.py` — 5 tests, passing.

**Verified**: frozen `deerflow-backend.exe --smoke-test` → `SMOKE OK`
(full gateway boots, `/health` → 200, clean exit).

### 2.3 Frontend desktop bridge (typechecks, never rendered in webview)

- `frontend/src/core/api/desktop-bridge.ts` — Tauri detection
  (`window.__TAURI_INTERNALS__`), `getDesktopPorts()` polls the `resolve_ports`
  IPC command (15s timeout).
- `frontend/src/components/desktop/titlebar.tsx` — frameless titlebar
  (drag region, min/max/close via dynamic `@tauri-apps/api/window` import).
- `frontend/src/typings/tauri.d.ts` — ambient types for the optional
  `@tauri-apps/api` (typecheck passes without the package installed).
- `pnpm typecheck` and `pnpm lint` both pass.

### 2.4 Tauri Rust shell (compiles, runs, launches)

- `desktop/src-tauri/` — Cargo.toml (tauri 2.11, plugins shell/dialog/fs/
  updater), build.rs, tauri.conf.json (frameless window, externalBin,
  updater config), capabilities/default.json, src/main.rs.
- `main.rs` — spawns the sidecar (candidate paths: exe-adjacent
  `binaries/` + source `src-tauri/binaries/`), reads port markers on a
  background thread, `resolve_ports` IPC, kills sidecar on window close.
- Icons generated: `desktop/src-tauri/icons/` (from a programmatically
  generated `desktop/icons/app-icon.png`).
- **`cargo check` and `cargo build` both pass** → `target/debug/uni-deer-desktop.exe`
  exists.
- **Launched successfully**: `uni-deer-desktop.exe` + `deerflow-backend.exe`
  both ran; the frozen sidecar booted the gateway from the bundled exe.

### 2.5 Build automation & CI

- `scripts/build_desktop.py` — 3 stages (icons/sidecar/frontend/tauri),
  `--dry-run`, `--stage`, installs the sidecar binary with the Tauri-required
  target-triple suffix (`deerflow-backend-x86_64-pc-windows-gnu.exe`).
- `.github/workflows/desktop-release.yml` — `sidecar-smoke` job + `build`
  matrix (macOS arm64/x64, Ubuntu 22.04, Windows) with `tauri-action`,
  signing secrets, `latest.json` publish.
- `backend/pyproject.toml` — added `desktop = ["pyinstaller>=6.0"]` extra;
  `uv.lock` regenerated.
- `docs/DESKTOP_BUILD.md` — full runbook (setup, signing, release, verify,
  troubleshooting).

---

## 3. What is NOT done / NOT verified (remaining work)

### 3.1 The last runtime blocker (WIP)

The desktop app launches and the sidecar boots, but the gateway **lifespan
fails** with:

```
ValueError: memory.manager_class='deermem' is not a registered backend name
(known: []) nor a resolvable 'pkg.mod:Cls' path
```

**Root cause**: `_scan_backends()` in
`deerflow/agents/memory/manager.py` discovers backends by **walking the
filesystem** (`_BACKENDS_DIR.iterdir()` + `__init__.py` check). PyInstaller
packs modules into its archive, so the real `backends/` directory tree does
not exist on disk in the frozen bundle → the scan finds nothing.

**Fix applied (LAST action before stopping)**: added the memory
`backends/` directory to the PyInstaller spec `datas`:

```python
(str(BACKEND_ROOT / "packages" / "harness" / "deerflow" / "agents" / "memory" / "backends"),
 "deerflow/agents/memory/backends"),
```

and **rebuilt + reinstalled** the sidecar into `desktop/src-tauri/binaries/`.

**NEXT STEP (unverified)**: relaunch the desktop app and confirm the
`deermem` error is gone and the gateway completes startup:

```bash
export PATH="$USERPROFILE/.cargo/bin:/c/msys64/mingw64/bin:$PATH"
cd C:/github/deer-flow/desktop/src-tauri
# kill any stragglers first
taskkill //F //IM uni-deer-desktop.exe 2>/dev/null; taskkill //F //IM deerflow-backend.exe 2>/dev/null
./target/debug/uni-deer-desktop.exe > /tmp/tauri-run5.log 2>&1 &
sleep 40
tasklist | grep -iE 'uni-deer|deerflow'          # both should be alive
grep -iE 'error|traceback|valueerror' /tmp/tauri-run5.log   # should be empty
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/health   # expect 200
```

If `deermem` still fails, check whether the `backends/` data actually landed
in the bundle:

```bash
ls backend/dist/deerflow-desktop/_internal/deerflow/agents/memory/backends/
```

If the directory is there but the scan still finds nothing, the issue may be
that `_BACKENDS_DIR` resolves to a different path in the frozen app
(`sys._MEIPASS` vs cwd) — check `_BACKENDS_DIR` in `manager.py` and, if
needed, set it relative to `sys._MEIPASS` when frozen.

### 3.2 Next.js standalone frontend (never built)

`frontend/.next/standalone` does not exist yet. The sidecar logs "Next.js
standalone output not found; skipping frontend child" — so the webview has no
content (blank window).

**To build it**:

```bash
cd C:/github/deer-flow/frontend
NEXT_CONFIG_BUILD_OUTPUT=standalone pnpm build
```

This produces `frontend/.next/standalone`. Then the desktop dist needs:

```bash
cd C:/github/deer-flow
python scripts/build_desktop.py --stage frontend
```

(`build_desktop.py` copies `.next/standalone` → `desktop/dist/` and the
`.next/static` assets.)

**Caveat**: the Next.js build needs env validation to pass. Use
`SKIP_ENV_VALIDATION=1` or a real `BETTER_AUTH_SECRET` if the build complains.

### 3.3 Release build (never run)

```bash
cd C:/github/deer-flow
python scripts/build_desktop.py          # full: icons + sidecar + frontend + tauri
```

This runs `cargo tauri build` → produces the installer
(`.msi`/`.exe` in `desktop/src-tauri/target/release/bundle/`).

**Placeholders still to fill** (before a real release):
- `desktop/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`:
  `REPLACE_WITH_TAURI_SIGNING_PUBLIC_KEY` (generate with
  `cargo tauri signer generate`)
- `plugins.updater.endpoints`:
  `https://github.com/YOUR_ORG/uni-deer/...` → real org
- `desktop/icons/app-icon.png` — currently a programmatic placeholder glyph;
  replace with a real 512×512 brand icon.

### 3.4 Rust shell runtime details to verify

- The dev-mode sidecar fallback (`python -m app.gateway.desktop_entry`)
  needs the backend importable — not relevant for the release bundle, but
  `pnpm tauri dev` from repo root may need `PYTHONPATH=backend`.
- WebView2 runtime: assumed preinstalled on Win10/11; if the window is blank
  even with `desktop/dist/` present, install the Evergreen WebView2 runtime.

---

## 4. File inventory (all new/created this effort)

| Path | Purpose |
| --- | --- |
| `backend/app/gateway/desktop_entry.py` | Desktop sidecar entry (gateway boot, ports, config bootstrap) |
| `backend/desktop_build.spec` | PyInstaller spec |
| `backend/tests/test_desktop_entry.py` | Sidecar unit tests (5 passing) |
| `backend/pyproject.toml` (+ `uv.lock`) | `desktop` extra (`pyinstaller`) |
| `backend/ruff.toml` | `*.spec` per-file-ignores |
| `frontend/src/core/api/desktop-bridge.ts` | Tauri detection + port polling |
| `frontend/src/components/desktop/titlebar.tsx` | Frameless titlebar |
| `frontend/src/typings/tauri.d.ts` | Ambient `@tauri-apps/api` types |
| `desktop/package.json`, `.gitignore` | Desktop npm project |
| `desktop/src-tauri/Cargo.toml`, `build.rs` | Rust manifest |
| `desktop/src-tauri/tauri.conf.json` | Window, sidecar, updater config |
| `desktop/src-tauri/capabilities/default.json` | Permissions |
| `desktop/src-tauri/src/main.rs` | Rust lifecycle manager |
| `desktop/src-tauri/icons/` | Generated icon set |
| `desktop/icons/app-icon.png` | Source icon (placeholder glyph) |
| `scripts/build_desktop.py` | 3-stage build orchestrator |
| `.github/workflows/desktop-release.yml` | CI release workflow |
| `docs/DESKTOP_BUILD.md` | Runbook |
| `bundle.md` | Original plan (edited for Next.js reality) |

---

## 5. Quick resume checklist (next session)

1. **Finish the deermem fix verification** (§3.1 commands) — the last
   unverified step; if the backends data didn't fix it, set `_BACKENDS_DIR`
   relative to `sys._MEIPASS` in the frozen case.
2. **Build the Next.js standalone** (§3.2) and reinstall the frontend dist.
3. **Relaunch** the desktop app — expect a real window with the UniDeer UI
   talking to the local gateway.
4. **Run the release build** (§3.3) → installer.
5. **Fill placeholders** (pubkey, endpoint URL, real icon).
6. **End-to-end manual verification** per `docs/DESKTOP_BUILD.md` §5:
   chat, tools, artifacts, graceful shutdown (no orphan processes).

---

## 6. Key gotchas learned (do not re-discover)

- The harness reads **`DEER_FLOW_HOME`**, not `UNI_DEER_HOME` (docs alias).
- Tauri `externalBin` needs the **target-triple suffix**
  (`deerflow-backend-x86_64-pc-windows-gnu.exe`).
- Tauri v2 config: `plugins.updater` is a **top-level** key (sibling of
  `app`/`bundle`); `bundle.createUpdaterArtifacts: true` is required for the
  updater.
- PyInstaller + dynamic scans (memory backends, middleware package, alembic
  migrations) need **both** hidden imports AND data-file collection.
- The config loader fails hard on unset `$VAR` — desktop bootstrap must
  regenerate invalid configs.
- Every Rust command needs:
  `export PATH="$USERPROFILE/.cargo/bin:/c/msys64/mingw64/bin:$PATH"`
