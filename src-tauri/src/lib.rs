mod app_state;
mod commands;
mod python_proc;
mod rpc_bridge;

use tauri::Manager;

use crate::app_state::AppState;
use crate::rpc_bridge::RpcBridge;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let handle = app.handle().clone();
            let rpc = RpcBridge::new(handle);
            app.manage(AppState {
                rpc: rpc.clone(),
                python: tokio::sync::Mutex::new(None),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::start_python,
            commands::stop_python,
            commands::rpc_call,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
