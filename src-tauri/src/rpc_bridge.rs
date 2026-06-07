use std::collections::HashMap;
use std::sync::Arc;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout};
use tokio::sync::{mpsc, Mutex};

/// One NDJSON message from Python to Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum RpcMessage {
    Request { id: u64, method: String, params: Value },
    Response { id: u64, result: Value },
    Event { event: String, data: Value },
    Error { id: u64, error: RpcErrorBody },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcErrorBody {
    pub code: String,
    pub message: String,
    #[serde(default)]
    pub detail: Value,
}

/// Bridge: holds stdin writer + event forwarder for a Python child process.
pub struct RpcBridge {
    app: AppHandle,
    stdin: Mutex<Option<ChildStdin>>,
    #[allow(dead_code)]
    line_tx: mpsc::UnboundedSender<String>,
    pending: Arc<Mutex<HashMap<u64, tokio::sync::oneshot::Sender<Value>>>>,
    next_id: Mutex<u64>,
}

impl RpcBridge {
    pub fn new(app: AppHandle) -> Arc<Self> {
        let (tx, mut rx) = mpsc::unbounded_channel::<String>();
        // 派一个 task 处理 stdin writer
        tokio::spawn(async move {
            while let Some(_line) = rx.recv().await {
                log::debug!("(stdin queue) {}", _line);
            }
        });
        Arc::new(Self {
            app,
            stdin: Mutex::new(None),
            line_tx: tx,
            pending: Arc::new(Mutex::new(HashMap::new())),
            next_id: Mutex::new(1),
        })
    }

    /// 在 Python 子进程启动后调用，把它的 stdin/stdout 接入桥。
    pub async fn attach(&self, stdin: ChildStdin, stdout: ChildStdout) {
        *self.stdin.lock().await = Some(stdin);

        // 启动 stdout reader
        let app = self.app.clone();
        let pending = self.pending.clone();
        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                if let Ok(msg) = serde_json::from_str::<RpcMessage>(&line) {
                    Self::handle_inbound(app.clone(), msg, pending.clone()).await;
                }
            }
            log::info!("python stdout EOF");
        });
    }

    async fn handle_inbound(
        app: AppHandle,
        msg: RpcMessage,
        pending: Arc<Mutex<HashMap<u64, tokio::sync::oneshot::Sender<Value>>>>,
    ) {
        match msg {
            RpcMessage::Event { event, data } => {
                log::debug!("emit to frontend: {} {:?}", event, data);
                let _ = app.emit(event, data);
            }
            RpcMessage::Response { id, result } => {
                if let Some(tx) = pending.lock().await.remove(&id) {
                    let _ = tx.send(result);
                }
            }
            RpcMessage::Error { id, error } => {
                log::warn!(
                    "python error id={} code={} msg={}",
                    id,
                    error.code,
                    error.message
                );
                if let Some(tx) = pending.lock().await.remove(&id) {
                    // 序列化成 Value 给前端，错误也作为 result 返回
                    let _ = tx.send(serde_json::json!({
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "detail": error.detail,
                        }
                    }));
                }
            }
            RpcMessage::Request { .. } => {
                log::warn!("unexpected request from python (python should not call us)");
            }
        }
    }

    /// Tauri 命令侧用：发请求给 Python，等响应。
    pub async fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        let mut next_id_guard = self.next_id.lock().await;
        let id = *next_id_guard;
        *next_id_guard += 1;
        drop(next_id_guard);

        let (tx, rx) = tokio::sync::oneshot::channel();
        self.pending.lock().await.insert(id, tx);

        let msg = serde_json::json!({
            "type": "request",
            "id": id,
            "method": method,
            "params": params,
        });
        let line = format!("{}\n", serde_json::to_string(&msg).unwrap());

        let mut stdin_guard = self.stdin.lock().await;
        let stdin = stdin_guard.as_mut().ok_or("python not running")?;
        stdin
            .write_all(line.as_bytes())
            .await
            .map_err(|e| e.to_string())?;
        stdin.flush().await.map_err(|e| e.to_string())?;

        let result = rx.await.map_err(|_| "response channel closed".to_string())?;
        Ok(result)
    }
}