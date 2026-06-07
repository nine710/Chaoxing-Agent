# 集成指南 — 接入 ChaoxingAgent RPC 子进程

> 如果你正在写**另一个程序**想通过 RPC 控制 ChaoxingAgent（或反过来，把它嵌入更大的系统），看这一份。

## 协议：NDJSON over stdin/stdout

ChaoxingAgent 的 Python 内核通过 stdio 跑 NDJSON 协议（每行一个 JSON 对象，`\n` 结尾）。`chaoxing_agent/rpc_types.py` 定义了 4 种消息类型。

### 消息定义

| `type` | 方向 | 必填字段 | 用途 |
|---|---|---|---|
| `request` | host → Python | `id`, `method`, `params` | 调用 RPC |
| `response` | Python → host | `id`, `result` | 成功 |
| `error` | Python → host | `id`, `error{code,message,detail}` | 失败（**不是 response.result**） |
| `event` | Python → host | `event`, `data` | 推送（`ready` / `paused` / `calibration_changed` / `config_changed` / `log`） |

### 启动

```bash
uv run python -m chaoxing_agent --rpc
```

子进程启动后第一件事是 emit 一个 `ready` 事件：

```json
{"type": "event", "event": "ready", "data": {"ts": "2026-06-07T..."}}
```

之后才进入主循环等待 `request`。**先发 `request` 会被忽略**（serve 主循环在 `emit("ready")` 之后才注册 handler）。

### 错误契约

Python 端的 RPC handler **抛异常**会变成 `error` 消息（**不**是 `response.result`）。host 必须把 `error` 消息转成失败状态：

```python
# host 端伪代码
async for line in child.stdout:
    msg = json.loads(line)
    if msg["type"] == "response":
        pending[msg["id"]].set_result(msg["result"])
    elif msg["type"] == "error":
        pending[msg["id"]].set_exception(RpcError(msg["error"]))
    elif msg["type"] == "event":
        forward_to_subscriber(msg["event"], msg["data"])
```

不要这样写（错误做法）：

```python
# 错误：把 error 当 response 处理
if msg["type"] == "response":
    pending[msg["id"]].set_result(msg["result"])  # 吞掉所有 error
```

### RPC method 清单（14 个）

详见 `chaoxing_agent/rpc_handlers.py::make_handlers`：

| method | params | 用途 |
|---|---|---|
| `ping` | `{}` | 健康检查；返回 `{"pong": true, "ts": ...}` |
| `list_windows` | `{"process_name": "..."} \| {"pid": 12345}` | 枚举目标应用顶层窗口 |
| `get_calibration` | `{}` | 当前标定状态（target hwnd / viewport / 最近截图） |
| `launch_calibration_wizard` | `{}` | 启动标定向导（独立子进程） |
| `start_run` | `{}` | 启动 AsyncStateMachine |
| `stop_run` | `{}` | 优雅停止 |
| `pause_decision` | `{"decision": "retry"\|"skip"\|"stop"}` | 解除 PauseGate |
| `list_trace_sessions` | `{"limit": 50}` | 列历史 session |
| `get_session_detail` | `{"session_id": "...", "step"?: int}` | session 详情 |
| `get_config` | `{}` | 读运行时配置 |
| `update_config` | `{"patch": {...}}` | 热更白名单字段（`timing` / `thresholds` / `runtime` / `selected`） |
| `get_model_services` | `{}` | 读模型服务配置 |
| `switch_model` | `{"role": "vision"\|"solver", "key": "..."}` | 多 provider registry 切换；**单 provider 结构会显式拒绝** |
| `test_model` | `{"role": "...", "key": "..."}` | 连通性测试 |

## Tauri 2 host 的实现参考

Tauri 2 shell 已经实现了 host 端，可以参考 `src-tauri/src/rpc_bridge.rs`：

- id 分配（`next_id: Mutex<u64>`）
- oneshot 关联表（`pending: HashMap<u64, oneshot::Sender<RpcResult>>`）
- `tokio::process::Command` 启子进程
- stdout 异步 reader + NDJSON 解析
- 子进程 `app.emit(event, data)` 转发到前端 webview

**Tauri 2 的反直觉事实**：`EventId` 是 `u32` 别名，无 `Drop`——`let _ = app.listen(...)` **不会**取消订阅，listener 一直存续到 AppHandle 销毁。

## Python 内核要求

- Python ≥ 3.10（`pyproject.toml::requires-python`）
- 依赖见 `requirements.txt` / `uv.lock`
- `config/config.json` 和 `config/model_services.json` 必须存在（首次 `uv run python main.py --init-config` 生成）
- `config/.env` 含 `VISION_API_KEY` / `SOLVER_API_KEY`

## 性能红线（要测的方法集成前必读）

| 项 | 红线 | 原因 |
|---|---|---|
| vision `enable_thinking` | **关闭** | mimo-v2.5 开思考后单次 30-40s（关闭 ~7s） |
| vision `max_tokens` | **≥ 3000** | 低于 3000 `finish=length` 空回 |
| solver `use_response_format` | **true** | 关闭 JSON mode 也空回 |
| solver `max_tokens` | **≥ 2000** | 同上 |
| solver `reasoning_effort` | `low` | 启用低深度思考，避免长 reasoning 拖慢 |

## 故障排查

### 子进程秒退 / `No module named chaoxing_agent.__main__`

Python 包没有 `__main__.py`。必须存在 `chaoxing_agent/__main__.py`（Tauri host 调 `python -m chaoxing_agent --rpc`）。

### 子进程跑起来但 ready 之后 5s 还没收到 response

`request` 的 id 是 `u64` 单调递增，Python 必须用同一 id 回 `response` 或 `error`。Python 端 handler 必须 `await` 异步操作（`start_run` 启动 AsyncStateMachine 是 fire-and-forget，但大多数 handler 是 `async def`）。

### Host 拿到 response 但 frontend 拿不到

Tauri host 在 `RpcBridge::handle_inbound` 收到 `event` 消息会 `app.emit(event, data)` 推到 webview。frontend 必须在 `tauri-bridge.ts` 里有 `listen(event, ...)` 注册；事件名大小写敏感。
