#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::{Duration, Instant},
};
use tauri::{Manager, State, WindowEvent};

const BACKEND_ADDR: &str = "127.0.0.1:8765";

#[derive(Default)]
struct BackendProcess {
    child: Mutex<Option<Child>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BackendHealth {
    status: String,
    gpu_available: bool,
    nvenc_available: bool,
}

fn project_root() -> Result<PathBuf, String> {
    if let Ok(root) = std::env::var("VAYA_PROJECT_ROOT") {
        return Ok(PathBuf::from(root));
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .ok_or_else(|| "Cannot resolve project root".to_string())
}

fn backend_dir() -> Result<PathBuf, String> {
    Ok(project_root()?.join("backend"))
}

fn read_backend_health() -> Option<BackendHealth> {
    let addr: SocketAddr = BACKEND_ADDR.parse().ok()?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(500)).ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(5)));

    stream
        .write_all(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .ok()?;

    let mut response = String::new();
    stream.read_to_string(&mut response).ok()?;

    if !response.starts_with("HTTP/1.1 200") && !response.starts_with("HTTP/1.0 200") {
        return None;
    }

    let body = response.split("\r\n\r\n").nth(1)?;
    serde_json::from_str::<BackendHealth>(body).ok()
}

fn ensure_backend_started(state: &BackendProcess) -> Result<(), String> {
    if read_backend_health().is_some() {
        return Ok(());
    }

    let backend_dir = backend_dir()?;
    if !backend_dir.exists() {
        return Err(format!(
            "Backend directory not found: {}",
            backend_dir.display()
        ));
    }

    let child = Command::new("uv")
        .args(["run", "python", "main.py"])
        .current_dir(&backend_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|err| format!("Failed to start backend with uv: {err}"))?;

    {
        let mut guard = state
            .child
            .lock()
            .map_err(|_| "Backend process lock poisoned".to_string())?;
        *guard = Some(child);
    }

    let deadline = Instant::now() + Duration::from_secs(15);
    while Instant::now() < deadline {
        if read_backend_health().is_some() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(500));
    }

    Err("Backend did not become healthy within 15 seconds".to_string())
}

fn stop_backend(state: &BackendProcess) {
    let Ok(mut guard) = state.child.lock() else {
        return;
    };

    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn open_path(path: &Path) -> Result<(), String> {
    let mut command = if cfg!(target_os = "windows") {
        let mut cmd = Command::new("explorer");
        cmd.arg(path);
        cmd
    } else if cfg!(target_os = "macos") {
        let mut cmd = Command::new("open");
        cmd.arg(path);
        cmd
    } else {
        let mut cmd = Command::new("xdg-open");
        cmd.arg(path);
        cmd
    };

    command
        .spawn()
        .map(|_| ())
        .map_err(|err| format!("Failed to open {}: {err}", path.display()))
}

#[tauri::command]
fn get_backend_status(state: State<'_, BackendProcess>) -> BackendHealth {
    if let Some(health) = read_backend_health() {
        return health;
    }

    if let Err(err) = ensure_backend_started(&state) {
        eprintln!("[vaya] {err}");
    }

    read_backend_health().unwrap_or(BackendHealth {
        status: "unavailable".to_string(),
        gpu_available: false,
        nvenc_available: false,
    })
}

#[tauri::command]
fn open_output_folder() -> Result<(), String> {
    let output_dir = project_root()?
        .join("backend")
        .join("storage")
        .join("output");
    fs::create_dir_all(&output_dir)
        .map_err(|err| format!("Failed to create output directory: {err}"))?;
    open_path(&output_dir)
}

#[tauri::command]
fn open_file_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Video files", &["mp4", "mkv", "mov", "webm", "avi"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess::default())
        .setup(|app| {
            let state = app.state::<BackendProcess>();
            if let Err(err) = ensure_backend_started(&state) {
                eprintln!("[vaya] {err}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            open_file_dialog,
            open_output_folder
        ])
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let state = window.state::<BackendProcess>();
                stop_backend(&state);
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run Vaya Tauri app");
}
