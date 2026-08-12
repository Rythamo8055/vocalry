#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let resource_dir = app.path().resource_dir()?;
            let data_dir = app.path().app_data_dir()?;
            fs::create_dir_all(data_dir.join("jobs"))?;

            let models_dir = resource_dir.join("models");
            fs::create_dir_all(&models_dir)?;

            let sidecar = app.shell().sidecar("8d-backend")?;
            sidecar
                .env("MODEL_DIR", &models_dir)
                .env("JOBS_DIR", data_dir.join("jobs"))
                .env("DB_PATH", data_dir.join("jobs.db"))
                .env("PORT", "8000")
                .spawn()?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running 8D Studio");
}
