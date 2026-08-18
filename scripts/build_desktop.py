"""One-command multi-stage build for the UniDeer desktop app.

Stages:
  1. PyInstaller the backend sidecar -> desktop/src-tauri/binaries/
  2. Build the Next.js frontend as a standalone server -> desktop/dist/
  3. cargo tauri build -> native installer (.msi/.exe, .dmg, .deb)

Usage:
    python scripts/build_desktop.py            # full build
    python scripts/build_desktop.py --dry-run  # print what would run
    python scripts/build_desktop.py --stage sidecar|frontend|tauri
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"
DESKTOP = REPO_ROOT / "desktop"
TAURI_BINARIES = DESKTOP / "src-tauri" / "binaries"
DESKTOP_DIST = DESKTOP / "dist"
STANDALONE = FRONTEND / ".next" / "standalone"
# Source icon (512x512 PNG) from which `tauri icon` generates the full set.
ICON_SOURCE = REPO_ROOT / "desktop" / "icons" / "app-icon.png"


def _run(cmd: list[str], cwd: Path, dry_run: bool) -> None:
    print(f"[build_desktop] {' '.join(cmd)}  (cwd={cwd})")
    if dry_run:
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def generate_icons(dry_run: bool) -> None:
    """Generate the Tauri icon set from a source 512x512 PNG.

    Requires `cargo tauri` (the CLI) and a source image at
    ``desktop/icons/app-icon.png``. Skipped when the source is absent so the
    rest of the build can still run.
    """
    if not ICON_SOURCE.exists():
        print(f"[build_desktop] icon source not found ({ICON_SOURCE}); skipping icon generation")
        return
    _run(["cargo", "tauri", "icon", str(ICON_SOURCE)], cwd=DESKTOP, dry_run=dry_run)


def build_sidecar(dry_run: bool) -> None:
    """PyInstaller the backend entry into desktop/src-tauri/binaries/."""
    TAURI_BINARIES.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(BACKEND / "desktop_build.spec"),
        ],
        cwd=BACKEND,
        dry_run=dry_run,
    )
    if not dry_run:
        dist_dir = BACKEND / "dist" / "deerflow-desktop"
        if not dist_dir.exists():
            raise SystemExit(f"PyInstaller output not found: {dist_dir}")
        # Copy the collected bundle next to the sidecar binary. Tauri's
        # externalBin expects the binary name with a target-triple suffix
        # (e.g. deerflow-backend-x86_64-pc-windows-gnu.exe), so copy the whole
        # bundle and then add the suffixed binary name.
        shutil.copytree(dist_dir, TAURI_BINARIES, dirs_exist_ok=True)
        _install_sidecar_binary(dist_dir, TAURI_BINARIES)


def _target_triple() -> str:
    """Return the rustc host triple (e.g. x86_64-pc-windows-gnu)."""
    import platform

    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    if sys.platform == "win32":
        return f"{arch}-pc-windows-gnu"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def _install_sidecar_binary(dist_dir: Path, target_dir: Path) -> None:
    """Copy the PyInstaller exe to the Tauri-expected triple-suffixed name.

    Tauri's externalBin resolution looks for
    ``binaries/<name>-<target-triple><ext>``; the PyInstaller output is named
    ``deerflow-backend<ext>``. Create the suffixed copy so ``cargo tauri
    build`` finds it.
    """
    ext = ".exe" if sys.platform == "win32" else ""
    plain = dist_dir / f"deerflow-backend{ext}"
    if not plain.exists():
        raise SystemExit(f"sidecar binary not found: {plain}")
    suffixed = target_dir / f"deerflow-backend-{_target_triple()}{ext}"
    shutil.copy2(plain, suffixed)
    print(f"[build_desktop] installed sidecar binary as {suffixed}")


def build_frontend(dry_run: bool) -> None:
    """Build the Next.js standalone server into desktop/dist/."""
    _run(
        [
            "pnpm",
            "build",
        ],
        cwd=FRONTEND,
        dry_run=dry_run,
    )
    if not dry_run:
        if not STANDALONE.exists():
            raise SystemExit("standalone output not found; is NEXT_CONFIG_BUILD_OUTPUT=standalone set?")
        DESKTOP_DIST.mkdir(parents=True, exist_ok=True)
        shutil.copytree(STANDALONE, DESKTOP_DIST, dirs_exist_ok=True)
        # Copy static assets (standalone output excludes .next/static).
        next_static = FRONTEND / ".next" / "static"
        if next_static.exists():
            shutil.copytree(next_static, DESKTOP_DIST / ".next" / "static", dirs_exist_ok=True)


def build_tauri(dry_run: bool) -> None:
    """cargo tauri build into native installers."""
    _run(["cargo", "tauri", "build"], cwd=DESKTOP, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="UniDeer desktop build")
    parser.add_argument("--dry-run", action="store_true", help="print stages without running")
    parser.add_argument(
        "--stage",
        choices=["icons", "sidecar", "frontend", "tauri", "all"],
        default="all",
        help="build only one stage (default: all)",
    )
    args = parser.parse_args()

    # Frontend standalone output requires the env var; set it for the build.
    os.environ.setdefault("NEXT_CONFIG_BUILD_OUTPUT", "standalone")

    if args.stage in ("icons", "all"):
        generate_icons(args.dry_run)
    if args.stage in ("sidecar", "all"):
        build_sidecar(args.dry_run)
    if args.stage in ("frontend", "all"):
        build_frontend(args.dry_run)
    if args.stage in ("tauri", "all"):
        build_tauri(args.dry_run)

    print("[build_desktop] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
