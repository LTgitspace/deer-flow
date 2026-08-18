//! UniDeer desktop shell — Tauri v2 sidecar lifecycle manager.
//!
//! Spawns the `deerflow-backend` sidecar (PyInstaller bundle or `python -m
//! app.gateway.desktop_entry`), reads the port markers from its stdout on a
//! background thread, and exposes them to the webview via IPC. On window
//! close the sidecar is terminated and reaped, guaranteeing no orphans.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};

use serde::Serialize;
use tauri::{Manager, WindowEvent};

/// Marker lines emitted by `desktop_entry.py` on stdout.
const GATEWAY_PORT_MARKER: &str = "DEERFLOW_PORT=";
const FRONTEND_PORT_MARKER: &str = "FRONTEND_PORT=";

/// Shared sidecar state: child handle + resolved ports.
#[derive(Default)]
struct SidecarState {
    child: Mutex<Option<Child>>,
    ports: Mutex<Option<ResolvedPorts>>,
}

#[derive(Clone, Serialize)]
struct ResolvedPorts {
    gateway_port: Option<u16>,
    frontend_port: Option<u16>,
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let state = Arc::new(SidecarState::default());
            app.manage(state.clone());
            spawn_sidecar(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<Arc<SidecarState>>() {
                    if let Ok(mut guard) = state.child.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
                // Tauri will close the window after this handler returns.
            }
        })
        .invoke_handler(tauri::generate_handler![resolve_ports])
        .run(tauri::generate_context!())
        .expect("error while running UniDeer desktop");
}

/// Spawn the backend sidecar and read its port markers on a background thread.
fn spawn_sidecar(state: Arc<SidecarState>) {
    let mut command = sidecar_command();
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .env("DEER_FLOW_AUTH_DISABLED", "1");

    let child = match command.spawn() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("[unideer] failed to spawn sidecar: {e}");
            return;
        }
    };
    *state.child.lock().unwrap() = Some(child);

    // Read markers on a background thread so the window opens immediately;
    // the webview polls `resolve_ports` until both ports are present.
    let reader_state = state.clone();
    std::thread::spawn(move || {
        let mut guard = reader_state.child.lock().unwrap();
        let stdout = match guard.as_mut().and_then(|c| c.stdout.take()) {
            Some(s) => s,
            None => return,
        };
        drop(guard); // release the child lock; we only need stdout now
        let reader = BufReader::new(stdout);
        let mut gateway_port: Option<u16> = None;
        let mut frontend_port: Option<u16> = None;

        for line in reader.lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => break,
            };
            if let Some(rest) = line.strip_prefix(GATEWAY_PORT_MARKER) {
                gateway_port = rest.trim().parse().ok();
            } else if let Some(rest) = line.strip_prefix(FRONTEND_PORT_MARKER) {
                frontend_port = rest.trim().parse().ok();
            } else {
                eprintln!("[unideer] sidecar: {line}");
            }
            if gateway_port.is_some() && frontend_port.is_some() {
                break;
            }
        }

        let ports = ResolvedPorts {
            gateway_port,
            frontend_port,
        };
        *reader_state.ports.lock().unwrap() = Some(ports.clone());
        eprintln!(
            "[unideer] sidecar ready: gateway={:?} frontend={:?}",
            ports.gateway_port, ports.frontend_port
        );
    });
}

/// Build the sidecar command: bundled `binaries/deerflow-backend` in
/// production, `python -m app.gateway.desktop_entry` in development.
fn sidecar_command() -> Command {
    let exe_dir = std::env::current_exe().ok().and_then(|exe| {
        exe.parent().map(|p| p.to_path_buf())
    });

    // Candidate locations for the bundled sidecar:
    // 1. next to the running exe (release: target/release/binaries/)
    // 2. the source-tree binaries dir (dev: desktop/src-tauri/binaries/)
    let mut candidates: Vec<std::path::PathBuf> = Vec::new();
    if let Some(dir) = exe_dir {
        candidates.push(dir.join("binaries").join(sidecar_name()));
    }
    candidates.push(
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("binaries")
            .join(sidecar_name()),
    );

    if let Some(path) = candidates.into_iter().find(|p| p.exists()) {
        let dir = path
            .parent()
            .unwrap_or(std::path::Path::new("."))
            .to_path_buf();
        let mut cmd = Command::new(path);
        cmd.current_dir(dir);
        cmd
    } else {
        // Dev fallback: run the source entry via python. The backend must
        // be importable from the current directory, so the Tauri process
        // is expected to be launched from the repo root.
        let mut cmd = Command::new("python");
        cmd.args(["-m", "app.gateway.desktop_entry"]);
        cmd
    }
}

fn sidecar_name() -> &'static str {
    #[cfg(target_os = "windows")]
    {
        "deerflow-backend.exe"
    }
    #[cfg(not(target_os = "windows"))]
    {
        "deerflow-backend"
    }
}

/// IPC: return the resolved desktop ports to the webview (polled by the
/// frontend after load).
#[tauri::command]
fn resolve_ports(state: tauri::State<'_, Arc<SidecarState>>) -> ResolvedPorts {
    state
        .ports
        .lock()
        .unwrap()
        .clone()
        .unwrap_or(ResolvedPorts {
            gateway_port: None,
            frontend_port: None,
        })
}
