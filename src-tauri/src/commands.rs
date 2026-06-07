use tauri::State;

use crate::app_state::AppState;
use crate::python_proc::PythonProc;

#[tauri::command]
pub async fn rpc_call(
    method: String,
    params: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    state.rpc.request(&method, params).await
}

#[tauri::command]
pub async fn start_python(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut guard = state.python.lock().await;
    if guard.is_some() {
        return Err("python already started".into());
    }
    let proc = PythonProc::new(state.rpc.clone());
    proc.start(&app).await?;
    *guard = Some(proc);
    Ok(())
}

#[tauri::command]
pub async fn stop_python(
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut guard = state.python.lock().await;
    if let Some(proc) = guard.take() {
        proc.stop().await?;
    }
    Ok(())
}
