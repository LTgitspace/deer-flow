# UniDeer Desktop Build & Release Runbook

The UniDeer desktop app is a **Tauri v2 shell** + **Python sidecar**:

```
Tauri (Rust) shell  ──spawns──▶  deerflow-backend (PyInstaller bundle)
     │                                  │  boots the full FastAPI Gateway
     │                                  │  + embedded LangGraph runtime
     │                                  │  + Next.js standalone server (child)
     ▼                                  ▼
  Webview (Next.js)  ◀──/api/*──  gateway rewrites (ephemeral port)
```

- **Zero-server model**: no Nginx, no Docker. `DEER_FLOW_AUTH_DISABLED=1`, local
  `LocalSandboxProvider`, runtime state under `~/.deer-flow/`.
- **Runtime home**: the harness reads `DEER_FLOW_HOME` (not the documented
  `UNI_DEER_HOME` alias) for the base dir — `desktop_entry.py` sets both.
- **Auto-updater**: Tauri v2 updater, fed by `latest.json` published to the
  GitHub Release by `tauri-action`.

---

## 1. Prerequisites (per build machine)

| Tool | Version | Notes |
| --- | --- | --- |
| Rust | stable (1.77+) | `rustup` — required for Tauri |
| Node.js | 22+ | frontend + Tauri CLI |
| pnpm | 10 | repo convention |
| Python | 3.12+ | backend |
| `uv` | latest | backend dependency management |
| PyInstaller | via `desktop` extra | `uv sync --extra desktop` |

Linux additionally needs webkit/GTK system packages:

```bash
sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf
```

---

## 2. One-time setup

### 2.1 Backend lockfile (keeps CI green)

The `desktop` extra (`pyinstaller`) must be in `uv.lock`:

```bash
cd backend
uv lock          # regenerates uv.lock with the desktop extra
uv sync --group dev --extra desktop
```

### 2.2 Signing keys (auto-updater)

```bash
# in desktop/src-tauri
cargo tauri signer generate -w ~/.tauri/uni-deer.key
```

This prints a **public key** (paste into `tauri.conf.json` → `bundle.updater.pubkey`)
and writes a **private key** file. Store the private key + passphrase as GitHub
secrets:

- `TAURI_SIGNING_PRIVATE_KEY` — contents of the `.key` file
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` — the passphrase

Never commit the private key. The public key is safe to commit.

### 2.3 App icon

Drop a **512×512 PNG** at `desktop/icons/app-icon.png`. The build generates the
full icon set via `cargo tauri icon` (the workflow runs this automatically).

### 2.4 Updater endpoint

`tauri.conf.json` → `bundle.updater.endpoints` must point at the real release
URL:

```json
"endpoints": [
  "https://github.com/<ORG>/uni-deer/releases/latest/download/latest.json"
]
```

Replace `<ORG>` with the actual GitHub organization/repo.

---

## 3. Local build

```bash
# one command (icons + sidecar + frontend + tauri)
python scripts/build_desktop.py

# or stage-by-stage
python scripts/build_desktop.py --stage icons
python scripts/build_desktop.py --stage sidecar
python scripts/build_desktop.py --stage frontend
python scripts/build_desktop.py --stage tauri

# dry run (print what would run without executing)
python scripts/build_desktop.py --dry-run
```

Outputs:

- Sidecar bundle: `backend/dist/deerflow-desktop/` → copied to
  `desktop/src-tauri/binaries/`
- Frontend standalone: `frontend/.next/standalone` → copied to `desktop/dist/`
- Installers: `desktop/src-tauri/target/release/bundle/`
  - Windows: `.msi` / `.exe`
  - macOS: `.dmg` / `.app`
  - Linux: `.deb` / `.AppImage`

### Local development run

```bash
cd desktop
pnpm install
# dev fallback: main.rs spawns `python -m app.gateway.desktop_entry`
# (backend must be importable; launch from repo root or set PYTHONPATH)
pnpm tauri dev
```

---

## 4. Release (CI)

The `.github/workflows/desktop-release.yml` workflow handles everything:

1. **`sidecar-smoke`** job — boots the real gateway + `/health` check on every
   PR and release tag (fast regression gate).
2. **`build`** job — matrix (macOS arm64/x64, Ubuntu 22.04, Windows):
   - PyInstaller sidecar
   - Next.js standalone build
   - `cargo tauri icon`
   - `tauri-action` → builds, signs, uploads artifacts, publishes the Release
     with `latest.json` (draft by default)

### To ship a release

```bash
git tag v2.1.0
git push origin v2.1.0
```

The workflow creates a **draft Release**. Inspect it, then click **Publish**
— publishing flips `latest.json` live and enables in-app auto-update.

### Required secrets

| Secret | Purpose |
| --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` | signs the updater artifacts |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | passphrase for the key |
| `GITHUB_TOKEN` | built-in; `contents: write` for release publish |

---

## 5. Verification

### Automated (CI + local)

```bash
# sidecar smoke test (boots gateway, /health, exit on signal)
cd backend && uv run python -m app.gateway.desktop_entry --smoke-test

# backend unit tests incl. desktop entry
cd backend && uv run pytest tests/test_desktop_entry.py -q

# frontend checks
cd frontend && pnpm typecheck && pnpm lint
```

### Manual

1. **Fresh-machine install**: install the generated `.msi`/`.exe`/`.dmg`/`.deb`
   on a machine **without** Python, Node, or Docker — it must work standalone.
2. **End-to-end chat**: send messages, verify streaming markdown, sub-agent
   cards, workspace diffs.
3. **Local tools**: run `ls`, `mkdir`, a small Python script in the
   `LocalSandboxProvider` workspace.
4. **Graceful shutdown**: close the window; verify **no lingering**
   `deerflow-backend`, `next-server`, or `python` processes (Task Manager /
   Activity Monitor).
5. **Auto-update**: install an older release, publish a newer one, verify the
   in-app updater prompt and signed install.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `uv sync` fails in CI | `uv.lock` missing the `desktop` extra — run `cd backend && uv lock` and commit it |
| Tauri build: `externalBin` not found | sidecar not built — run `python scripts/build_desktop.py --stage sidecar` first |
| Updater: "invalid signature" | pubkey in `tauri.conf.json` does not match `TAURI_SIGNING_PRIVATE_KEY` — regenerate the key pair and update both |
| Updater: 404 on `latest.json` | Release not published (draft) or endpoint URL wrong — publish the draft / fix `<ORG>` |
| Webview blank in dev | Next.js standalone not built — run `NEXT_CONFIG_BUILD_OUTPUT=standalone pnpm build` |
| `python -m app.gateway.desktop_entry` fails to import | run from `backend/` or set `PYTHONPATH=backend` (dev fallback path in `main.rs`) |
| Runtime state lands in `dist/.../.deer-flow` instead of `~/.deer-flow` | `DEER_FLOW_HOME` not set — `desktop_entry.py` sets it, but manual runs must export it (the harness reads `DEER_FLOW_HOME`, not `UNI_DEER_HOME`) |
