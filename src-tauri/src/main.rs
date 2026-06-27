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
use tauri::{AppHandle, Manager, State, WindowEvent};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_ADDR: &str = "127.0.0.1:8765";
const BACKEND_SIDECAR_NAME: &str = "vaya-backend";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BuildProfile {
    Debug,
    Release,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum BackendLaunchPlan {
    Sidecar {
        name: String,
    },
    Uv {
        program: String,
        args: Vec<String>,
        cwd: PathBuf,
    },
}

enum ManagedBackendChild {
    Process(Child),
    Sidecar(CommandChild),
}

#[derive(Default)]
struct BackendProcess {
    child: Mutex<Option<ManagedBackendChild>>,
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

fn current_build_profile() -> BuildProfile {
    if cfg!(debug_assertions) {
        BuildProfile::Debug
    } else {
        BuildProfile::Release
    }
}

fn backend_launch_plan(profile: BuildProfile, backend_dir: PathBuf) -> BackendLaunchPlan {
    match profile {
        BuildProfile::Release => BackendLaunchPlan::Sidecar {
            name: BACKEND_SIDECAR_NAME.to_string(),
        },
        BuildProfile::Debug => BackendLaunchPlan::Uv {
            program: "uv".to_string(),
            args: vec![
                "run".to_string(),
                "python".to_string(),
                "main.py".to_string(),
            ],
            cwd: backend_dir,
        },
    }
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

fn ensure_backend_started(app: &AppHandle, state: &BackendProcess) -> Result<(), String> {
    if read_backend_health().is_some() {
        return Ok(());
    }

    let backend_dir = backend_dir()?;
    let plan = backend_launch_plan(current_build_profile(), backend_dir);
    let child = match plan {
        BackendLaunchPlan::Sidecar { name } => {
            let data_dir = app
                .path()
                .app_local_data_dir()
                .map_err(|err| format!("Cannot resolve app data directory: {err}"))?;
            fs::create_dir_all(&data_dir)
                .map_err(|err| format!("Failed to create backend data directory: {err}"))?;
            let config_path = data_dir.join("config.yaml");

            let (mut rx, child) = app
                .shell()
                .sidecar(name)
                .map_err(|err| format!("Failed to prepare backend sidecar: {err}"))?
                .env("VAYA_DATA_DIR", data_dir)
                .env("VAYA_CONFIG_PATH", config_path)
                .spawn()
                .map_err(|err| format!("Failed to start backend sidecar: {err}"))?;

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            eprintln!("[vaya-backend] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[vaya-backend] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });

            ManagedBackendChild::Sidecar(child)
        }
        BackendLaunchPlan::Uv { program, args, cwd } => {
            if !cwd.exists() {
                return Err(format!("Backend directory not found: {}", cwd.display()));
            }

            let child = Command::new(program)
                .args(args)
                .current_dir(cwd)
                .stdin(Stdio::null())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .spawn()
                .map_err(|err| format!("Failed to start backend with uv: {err}"))?;

            ManagedBackendChild::Process(child)
        }
    };

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

    if let Some(child) = guard.take() {
        match child {
            ManagedBackendChild::Process(mut process) => {
                let _ = process.kill();
                let _ = process.wait();
            }
            ManagedBackendChild::Sidecar(child) => {
                let _ = child.kill();
            }
        }
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
fn get_backend_status(app: AppHandle, state: State<'_, BackendProcess>) -> BackendHealth {
    if let Some(health) = read_backend_health() {
        return health;
    }

    if let Err(err) = ensure_backend_started(&app, &state) {
        eprintln!("[vaya] {err}");
    }

    read_backend_health().unwrap_or(BackendHealth {
        status: "unavailable".to_string(),
        gpu_available: false,
        nvenc_available: false,
    })
}

#[tauri::command]
fn open_output_folder(app: AppHandle) -> Result<(), String> {
    let output_dir = match current_build_profile() {
        BuildProfile::Release => app
            .path()
            .app_local_data_dir()
            .map_err(|err| format!("Cannot resolve app data directory: {err}"))?
            .join("output"),
        BuildProfile::Debug => project_root()?
            .join("backend")
            .join("storage")
            .join("output"),
    };
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
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess::default())
        .setup(|app| {
            let state = app.state::<BackendProcess>();
            if let Err(err) = ensure_backend_started(app.handle(), &state) {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_build_uses_bundled_sidecar() {
        let plan = backend_launch_plan(
            BuildProfile::Release,
            PathBuf::from("D:/reference2/vaya/backend"),
        );

        assert_eq!(
            plan,
            BackendLaunchPlan::Sidecar {
                name: "vaya-backend".to_string()
            }
        );
    }

    #[test]
    fn debug_build_uses_uv_from_backend_directory() {
        let backend_dir = PathBuf::from("D:/reference2/vaya/backend");
        let plan = backend_launch_plan(BuildProfile::Debug, backend_dir.clone());

        assert_eq!(
            plan,
            BackendLaunchPlan::Uv {
                program: "uv".to_string(),
                args: vec![
                    "run".to_string(),
                    "python".to_string(),
                    "main.py".to_string()
                ],
                cwd: backend_dir,
            }
        );
    }
}
