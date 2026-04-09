use tauri::Manager;
use std::time::Duration;

/// Spawn the FastAPI backend sidecar and wait for it to be ready
fn start_backend(app: &tauri::AppHandle) -> Result<(), String> {
    // Spawn the sidecar process
    let sidecar = app
        .shell()
        .sidecar("finai-backend")
        .map_err(|e| format!("Failed to create sidecar command: {}", e))?;

    let (_rx, _child) = sidecar
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

    // Poll health endpoint until backend is ready (max 20 seconds)
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| format!("HTTP client error: {}", e))?;

    for attempt in 0..40 {
        std::thread::sleep(Duration::from_millis(500));
        match client.get("http://127.0.0.1:9200/health").send() {
            Ok(resp) if resp.status().is_success() => {
                println!("Backend ready after {} attempts", attempt + 1);
                return Ok(());
            }
            _ => {
                if attempt % 4 == 0 {
                    println!("Waiting for backend... (attempt {})", attempt + 1);
                }
            }
        }
    }

    Err("Backend failed to start within 20 seconds".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // Start backend in a separate thread to avoid blocking the UI
            std::thread::spawn(move || {
                match start_backend(&handle) {
                    Ok(()) => println!("FinAI backend started successfully"),
                    Err(e) => eprintln!("Backend startup error: {}", e),
                }
            });

            // Navigate main window to the backend-served frontend
            // (during dev, devUrl is used; in production, frontendDist is served)
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_title("FinAI Platform - Financial Intelligence");
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running FinAI Desktop");
}
