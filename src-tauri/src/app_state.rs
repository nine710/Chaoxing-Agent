use std::sync::Arc;
use tokio::sync::Mutex;

use crate::python_proc::PythonProc;
use crate::rpc_bridge::RpcBridge;

pub struct AppState {
    pub rpc: Arc<RpcBridge>,
    pub python: Mutex<Option<PythonProc>>,
}