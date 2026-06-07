use std::process::Stdio;
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::Mutex;

use crate::rpc_bridge::RpcBridge;

pub struct PythonProc {
    pub child: Mutex<Option<tokio::process::Child>>,
    pub rpc: Arc<RpcBridge>,
}

impl PythonProc {
    pub fn new(rpc: Arc<RpcBridge>) -> Self {
        Self {
            child: Mutex::new(None),
            rpc,
        }
    }

    /// 启动 Python 子进程（uv run python -m chaoxing_agent --rpc）。
    /// 等到 5 秒内出现 `{"event": "ready"}` 事件才返回。
    pub async fn start(&self, app: &AppHandle) -> Result<(), String> {
        // 先订阅一次 ready 事件
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<serde_json::Value>();
        let app_for_listener = app.clone();
        let tx_for_listener = tx.clone();
        tauri::async_runtime::spawn(async move {
            use tauri::Listener;
            let _ = app_for_listener.listen("ready", move |event| {
                let payload: serde_json::Value =
                    serde_json::from_str(event.payload()).unwrap_or(serde_json::json!({}));
                let _ = tx_for_listener.send(payload);
            });
        });

        // 探查 Python 启动方式
        let cmd = "uv";

        let mut child = Command::new(cmd)
            .arg("run")
            .arg("python")
            .arg("-m")
            .arg("chaoxing_agent")
            .arg("--rpc")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .map_err(|e| format!("failed to spawn python: {}", e))?;

        let stdin = child.stdin.take().ok_or("no stdin".to_string())?;
        let stdout = child.stdout.take().ok_or("no stdout".to_string())?;
        let stderr = child.stderr.take().ok_or("no stderr".to_string())?;

        // 把 stderr 转发到 log
        let app_for_log = app.clone();
        tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                log::info!("[python stderr] {}", line);
                let _ = app_for_log.emit(
                    "log",
                    serde_json::json!({
                        "level": "INFO",
                        "message": line,
                        "ts": unix_secs_now(),
                    }),
                );
            }
        });

        self.rpc.attach(stdin, stdout).await;

        // 等 ready 事件（最多 5 秒）
        match tokio::time::timeout(std::time::Duration::from_secs(5), rx.recv()).await {
            Ok(Some(_)) => {
                log::info!("python ready");
            }
            Ok(None) => {
                let _ = child.kill().await;
                return Err("ready channel closed before ready event".into());
            }
            Err(_) => {
                let _ = child.kill().await;
                return Err("python did not send ready event within 5s".into());
            }
        }

        *self.child.lock().await = Some(child);
        Ok(())
    }

    pub async fn stop(&self) -> Result<(), String> {
        let mut guard = self.child.lock().await;
        if let Some(mut child) = guard.take() {
            let _ = child.kill().await;
        }
        Ok(())
    }
}

fn unix_secs_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{}", secs)
}
