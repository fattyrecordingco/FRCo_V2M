#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::{self, OpenOptions};
use std::io::Write;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn spawn_backend(app: &tauri::App) -> Option<Child> {
    let backend_dir = resolve_backend_dir(app)?;
    let data_root = resolve_data_root(app);
    let log_file = data_root.join("logs").join("backend-launch.log");
    if let Some(parent) = log_file.parent() {
        let _ = fs::create_dir_all(parent);
    }

    let commands = backend_command_candidates();
    for (command, args) in commands {
        let mut cmd = Command::new(&command);
        cmd.args(args.iter())
            .current_dir(&backend_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .env("VINS_PROJECT_ROOT", data_root.to_string_lossy().to_string());
        #[cfg(target_os = "windows")]
        cmd.creation_flags(0x08000000);

        match cmd.spawn() {
            Ok(mut child) => {
                thread::sleep(Duration::from_millis(900));
                match child.try_wait() {
                    Ok(Some(status)) => {
                        append_log(
                            &log_file,
                            &format!("backend command '{}' exited early: {}", command, status),
                        );
                        continue;
                    }
                    Ok(None) => {
                        append_log(
                            &log_file,
                            &format!(
                                "backend started with command '{}' in {}",
                                command,
                                backend_dir.display()
                            ),
                        );
                        return Some(child);
                    }
                    Err(err) => {
                        append_log(
                            &log_file,
                            &format!("backend try_wait failed for '{}': {}", command, err),
                        );
                    }
                }
            }
            Err(err) => {
                append_log(
                    &log_file,
                    &format!("backend spawn failed for '{}': {}", command, err),
                );
            }
        }
    }

    append_log(&log_file, "backend did not start with any command candidate");
    None
}

fn backend_command_candidates() -> Vec<(String, Vec<String>)> {
    if let Ok(raw) = std::env::var("VINS_BACKEND_CMD") {
        let parts: Vec<String> = raw.split_whitespace().map(ToString::to_string).collect();
        if let Some((command, args)) = parts.split_first() {
            return vec![(command.clone(), args.to_vec())];
        }
    }
    let uvicorn_args = vec![
        "-m".to_string(),
        "uvicorn".to_string(),
        "app.main:app".to_string(),
        "--host".to_string(),
        "127.0.0.1".to_string(),
        "--port".to_string(),
        "8000".to_string(),
    ];
    vec![
        ("python".to_string(), uvicorn_args.clone()),
        (
            "py".to_string(),
            vec!["-3.11".to_string()]
                .into_iter()
                .chain(uvicorn_args.clone())
                .collect(),
        ),
        (
            "py".to_string(),
            vec!["-3".to_string()]
                .into_iter()
                .chain(uvicorn_args.clone())
                .collect(),
        ),
        (
            "py".to_string(),
            uvicorn_args,
        ),
    ]
}

fn resolve_data_root(app: &tauri::App) -> PathBuf {
    if let Ok(dir) = app.path().app_local_data_dir() {
        let target = dir.join("vins-data");
        let _ = fs::create_dir_all(&target);
        return target;
    }
    if let Ok(dir) = std::env::current_dir() {
        let fallback = dir.join("vins-data");
        let _ = fs::create_dir_all(&fallback);
        return fallback;
    }
    PathBuf::from(".")
}

fn resolve_backend_dir(app: &tauri::App) -> Option<PathBuf> {
    if let Ok(dir) = std::env::var("VINS_BACKEND_DIR") {
        let path = PathBuf::from(dir);
        if path.exists() {
            return Some(path);
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        if let Some(found) = find_backend_from(cwd.as_path()) {
            return Some(found);
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(found) = find_backend_from(exe.as_path()) {
            return Some(found);
        }
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidates = [
            resource_dir.join("backend"),
            resource_dir.join("_up_").join("backend"),
            resource_dir.join("_up_").join("_up_").join("backend"),
        ];
        for candidate in candidates {
            if candidate.exists() {
                return Some(candidate);
            }
        }
        if let Some(found) = find_backend_from(resource_dir.as_path()) {
            return Some(found);
        }
    }
    None
}

fn find_backend_from(base: &Path) -> Option<PathBuf> {
    for ancestor in base.ancestors() {
        let candidate = ancestor.join("backend");
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

fn append_log(log_file: &Path, message: &str) {
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_file) {
        let _ = writeln!(file, "{}", message);
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let state = app.state::<BackendProcess>();
            if let Some(child) = spawn_backend(app) {
                if let Ok(mut guard) = state.0.lock() {
                    *guard = Some(child);
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let app = window.app_handle();
                let maybe_child = {
                    let state = app.state::<BackendProcess>();
                    let candidate = if let Ok(mut guard) = state.0.lock() {
                        guard.take()
                    } else {
                        None
                    };
                    candidate
                };
                if let Some(mut child) = maybe_child {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running VINS desktop app");
}
