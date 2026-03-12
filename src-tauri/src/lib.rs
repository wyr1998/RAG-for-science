use std::time::Duration;

use anyhow::anyhow;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::{process::CommandEvent, ShellExt};
use tokio::time::sleep;

fn spawn_backend(app: &AppHandle) -> anyhow::Result<()> {
    // Resolve the Tauri resource directory (where bundle.resources end up)
    let resource_dir = app.path().resource_dir()?;

    // These paths come from bundle.resources in tauri.conf.json (resources/backend/ -> backend/)
    let backend_resources_dir = resource_dir.join("backend");
    let bundled_jre_dir = backend_resources_dir.join("jdk-17.0.18+8-jre");
    let pdffigures2_dir = backend_resources_dir.join("pdffigures2");

    let sidecar = app
        .shell()
        .sidecar("backend")?
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .env(
            "BUNDLED_JRE_DIR",
            bundled_jre_dir.to_string_lossy().to_string(),
        )
        .env(
            "PDFFIGURES2_DIR",
            pdffigures2_dir.to_string_lossy().to_string(),
        );

    let (mut rx, _child) = sidecar.spawn()?;

    // Drain sidecar stdout/stderr and log events so we can see backend errors.
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match &event {
                CommandEvent::Stdout(line) => {
                    // line: &Vec<u8>
                    let text = String::from_utf8_lossy(line);
                    println!("[backend stdout] {}", text);
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(line);
                    eprintln!("[backend stderr] {}", text);
                }
                CommandEvent::Error(err) => {
                    eprintln!("[backend error] {}", err);
                }
                CommandEvent::Terminated(status) => {
                    eprintln!("[backend terminated] {:?}", status);
                }
                other => {
                    println!("[backend event] {:?}", other);
                }
            }
        }
    });

    Ok(())
}

async fn wait_for_backend() -> bool {
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };

    let deadline = std::time::Instant::now() + Duration::from_secs(20);
    while std::time::Instant::now() < deadline {
        if let Ok(resp) = client
            .get("http://127.0.0.1:8000/health")
            .send()
            .await
        {
            if resp.status().is_success() {
                return true;
            }
        }
        // Use Tokio's sleep, not tauri::async_runtime::sleep
        sleep(Duration::from_millis(250)).await;
    }
    false
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();
            spawn_backend(&handle)?;
            tauri::async_runtime::spawn(async move {
                let _ = wait_for_backend().await;
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}