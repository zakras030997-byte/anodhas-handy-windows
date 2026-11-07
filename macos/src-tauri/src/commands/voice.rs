//! One local worker per request. Dictation does not share this lock or process.
use serde_json::Value;
#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;
use std::{
    io::{Read, Write},
    process::{Child, Command, Stdio},
    sync::{Mutex, OnceLock},
    time::Duration,
};
use tauri::Manager;
static WORKER: OnceLock<Mutex<Option<Child>>> = OnceLock::new();
static CANCELLED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
static BUSY: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
struct BusyGuard;
impl Drop for BusyGuard {
    fn drop(&mut self) {
        BUSY.store(false, std::sync::atomic::Ordering::SeqCst);
    }
}

#[tauri::command]
#[specta::specta]
pub async fn voice_call(
    app: tauri::AppHandle,
    action: String,
    payload: String,
) -> Result<String, String> {
    let allowed = [
        "list",
        "storage",
        "import_file",
        "history",
        "history_detail",
        "import",
        "approve",
        "generate",
        "output",
    ];
    if !allowed.contains(&action.as_str()) {
        return Err("Unsupported voice operation".into());
    }
    if BUSY.swap(true, std::sync::atomic::Ordering::SeqCst) {
        return Err("Voice operation already running".into());
    }
    CANCELLED.store(false, std::sync::atomic::Ordering::SeqCst);
    let root = crate::portable::app_data_dir(&app).map_err(|_| {
        BUSY.store(false, std::sync::atomic::Ordering::SeqCst);
        "Cannot locate voice storage".to_string()
    })?;
    let script = app
        .path()
        .resolve(
            "resources/voice/service.py",
            tauri::path::BaseDirectory::Resource,
        )
        .map_err(|_| {
            BUSY.store(false, std::sync::atomic::Ordering::SeqCst);
            "Voice component missing".to_string()
        })?;
    let bundled_runtime = app
        .path()
        .resolve("voice-runtime", tauri::path::BaseDirectory::Resource)
        .map_err(|_| {
            BUSY.store(false, std::sync::atomic::Ordering::SeqCst);
            "Voice runtime path unavailable".to_string()
        })?;
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = BusyGuard;
        let payload: Value =
            serde_json::from_str(&payload).map_err(|_| "Invalid request".to_string())?;
        let _ = std::fs::create_dir_all(root.join("voice"));
        let _ = std::fs::write(root.join("voice/phase.json"), b"{\"phase\":\"working\"}");
        let portable = bundled_runtime.join("python/bin/python3").is_file();
        let runtime = if portable {
            bundled_runtime
        } else {
            root.join("voice-runtime")
        };
        let python = if portable {
            runtime.join("python/bin/python3")
        } else {
            runtime.join("venv/bin/python")
        };
        let mut command = Command::new(python);
        if portable {
            command.env("PYTHONPATH", runtime.join("site-packages"));
        }
        let mut child = command
            .arg(script)
            .arg(root.join("voice"))
            .arg(&runtime)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONNOUSERSITE", "1")
            .env("HF_HUB_OFFLINE", "1")
            .env("TRANSFORMERS_OFFLINE", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| "Local voice runtime is not installed".to_string())?;
        let request = serde_json::to_vec(&serde_json::json!({"action":action,"payload":payload}))
            .map_err(|_| "Invalid request".to_string())?;
        let sent = child
            .stdin
            .take()
            .ok_or("Cannot send request")
            .and_then(|mut input| input.write_all(&request).map_err(|_| "Cannot send request"));
        if let Err(e) = sent {
            let _ = child.kill();
            let _ = child.wait();
            return Err(e.to_string());
        }
        *WORKER
            .get_or_init(|| Mutex::new(None))
            .lock()
            .map_err(|_| "Worker unavailable")? = Some(child);
        let start = std::time::Instant::now();
        loop {
            {
                let mut slot = WORKER
                    .get_or_init(|| Mutex::new(None))
                    .lock()
                    .map_err(|_| "Worker unavailable")?;
                let c = slot.as_mut().ok_or("Worker missing")?;
                if CANCELLED.load(std::sync::atomic::Ordering::SeqCst)
                    || start.elapsed() > Duration::from_secs(600)
                {
                    let _ = c.kill();
                }
                if c.try_wait()
                    .map_err(|_| "Cannot check voice worker")?
                    .is_some()
                {
                    let mut c = slot.take().ok_or("Worker missing")?;
                    let mut output = String::new();
                    if let Some(stdout) = c.stdout.take() {
                        stdout
                            .take(1_000_000)
                            .read_to_string(&mut output)
                            .map_err(|_| "Cannot read voice result")?;
                    }
                    let result: Value = serde_json::from_str(&output)
                        .map_err(|_| "Voice operation cancelled or failed")?;
                    return if result["ok"] == true {
                        Ok(result["result"].to_string())
                    } else {
                        Err("Voice operation failed; check input and local model".into())
                    };
                }
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    })
    .await
    .map_err(|_| "Voice worker failed".to_string())?
}

#[tauri::command]
#[specta::specta]
pub fn voice_cancel() -> Result<(), String> {
    CANCELLED.store(true, std::sync::atomic::Ordering::SeqCst);
    if let Some(c) = WORKER
        .get_or_init(|| Mutex::new(None))
        .lock()
        .map_err(|_| "Worker unavailable")?
        .as_mut()
    {
        c.kill().map_err(|_| "Cannot cancel voice worker")?;
    }
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub fn voice_export(app: tauri::AppHandle, id: String, destination: String) -> Result<(), String> {
    if id.len() != 32 || !id.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("Invalid audio identifier".into());
    }
    let src = crate::portable::app_data_dir(&app)
        .map_err(|_| "Cannot locate audio")?
        .join("voice/outputs")
        .join(format!("{id}.wav"));
    let mut input = std::fs::File::open(src).map_err(|_| "Audio missing")?;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    options.mode(0o600);
    let mut output = options
        .open(destination)
        .map_err(|_| "Choose a new file name; existing files are never overwritten")?;
    std::io::copy(&mut input, &mut output).map_err(|_| "Cannot save audio")?;
    output
        .sync_all()
        .map_err(|_| "Cannot finish saving audio".to_string())
}

#[tauri::command]
#[specta::specta]
pub fn voice_phase(app: tauri::AppHandle) -> String {
    if !BUSY.load(std::sync::atomic::Ordering::SeqCst) {
        return "idle".into();
    }
    let phase = crate::portable::app_data_dir(&app)
        .ok()
        .and_then(|r| std::fs::read_to_string(r.join("voice/phase.json")).ok())
        .and_then(|v| serde_json::from_str::<Value>(&v).ok())
        .and_then(|v| v["phase"].as_str().map(str::to_string));
    match phase.as_deref() {
        Some("loading") => "loading".into(),
        Some("generating") => "generating".into(),
        _ => "working".into(),
    }
}

/// Open only the application's known voice folders, never a frontend-supplied path.
#[tauri::command]
#[specta::specta]
pub fn voice_open_folder(app: tauri::AppHandle, target: String) -> Result<(), String> {
    let root = crate::portable::app_data_dir(&app)
        .map_err(|_| "Cannot locate voice storage")?
        .join("voice");
    let path = match target.as_str() {
        "references" => root.join("profiles"),
        "outputs" => root.join("outputs"),
        "root" => root,
        _ => return Err("Unknown voice folder".into()),
    };
    std::fs::create_dir_all(&path).map_err(|_| "Cannot prepare voice folder")?;
    #[cfg(target_os = "macos")]
    let status = Command::new("/usr/bin/open").arg(&path).status();
    #[cfg(target_os = "windows")]
    let status = Command::new("explorer").arg(&path).status();
    #[cfg(target_os = "linux")]
    let status = Command::new("xdg-open").arg(&path).status();
    if status.map_err(|_| "Cannot open voice folder")?.success() {
        Ok(())
    } else {
        Err("Cannot open voice folder".into())
    }
}
