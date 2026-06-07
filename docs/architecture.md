# 架构

> 给接手者（包括未来的自己）看的 5 分钟能搞懂的整体设计。

## 一句话总结

**Tauri 2 桌面壳** + **React 前端** + **Python 子进程（NDJSON RPC）** 三层组合。
Tauri 负责窗口/打包/安全，React 负责 UI，Python 负责所有 Windows 自动化逻辑（截图、视觉、点击、状态机）。

## 进程拓扑

```
┌──────────────────────────────────────────────────────────┐
│  ChaoxingAgent.exe  (Tauri 2, Rust)                       │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Webview (Chromium)  ←→  React + TS + Tailwind     │  │
│  │  invoke('rpc_call', ...)  ↕  IPC 事件              │  │
│  └────────────────────────────────────────────────────┘  │
│           │  Tauri command (rpc_bridge.rs)                │
│           ▼                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │  RpcBridge  (Rust)                                 │  │
│  │   - pending: HashMap<id, oneshot::Sender<Result>>   │  │
│  │   - stdin writer  →  Python child stdin (NDJSON)   │  │
│  │   - stdout reader →  Python child stdout (NDJSON)  │  │
│  └────────────────────────────────────────────────────┘  │
│           │  tokio::process::Command (uv run ...)         │
│           ▼                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Python child  (uv run python -m chaoxing_agent    │  │
│  │                 --rpc)                              │  │
│  │   - __main__.py: argparse + HandlerContext + 14    │  │
│  │     RPC handlers + RpcServer.serve()                │  │
│  │   - core/*: 截图、坐标映射、点击、状态机           │  │
│  │   - models/*: OpenAI 兼容客户端（vision + solver） │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 关键目录

| 路径 | 职责 |
|---|---|
| `src-tauri/` | Tauri 2 Rust 壳（commands、python 子进程管理、NDJSON 桥） |
| `src-tauri/src/python_proc.rs` | `uv run python -m chaoxing_agent --rpc` 启动 + 5s ready 握手 |
| `src-tauri/src/rpc_bridge.rs` | stdin/stdout 双向 NDJSON、id 分配、oneshot 关联表 |
| `web/` | React + TS + Tailwind 前端；`lib/tauri-bridge.ts` 封装 invoke |
| `chaoxing_agent/__main__.py` | **Python 子进程唯一入口**（解析 `--rpc`、构造 HandlerContext、`emit("ready")` 后 serve） |
| `chaoxing_agent/rpc_server.py` | NDJSON 服务端：`asyncio` 读 stdin 一行行 dispatch 到 handler；emit 写 stdout |
| `chaoxing_agent/rpc_handlers.py` | 14 个 RPC handler 集合（ping / list_windows / start_run / ...） |
| `chaoxing_agent/async_state_machine.py` | 异步状态机；通过 `PauseGate` 异步等待前端决策 |
| `chaoxing_agent/core/` | 截图、坐标映射、点击、env、错误、trace 等基础能力 |
| `chaoxing_agent/models/` | OpenAI 兼容客户端 + vision/solver 调用封装 |
| `config/` | 运行时配置（详见 `config.json.example.md`） |
| `tests/` | pytest 全集（24 个文件） |
| `docs/superpowers/` | 临时 plan/spec（已被 `.gitignore` 排除） |

## NDJSON 协议（4 种消息）

Python ↔ Rust 之间。每行一个 JSON 对象，`\n` 分隔。

| type | 方向 | 字段 | 说明 |
|---|---|---|---|
| `request` | Rust → Python | `id, method, params` | RPC 调用 |
| `response` | Python → Rust | `id, result` | 成功响应 |
| `error` | Python → Rust | `id, error{code,message,detail}` | **走 Result::Err，不 smuggle 成 success** |
| `event` | Python → Rust | `event, data` | 推给前端（如 `ready` / `paused` / `calibration_changed`） |

Rust 侧 `RpcBridge::request` 收到 `error` 时**关闭 oneshot 的 Err 分支**，`commands::rpc_call` 的 Tauri 命令返回 `Result::Err(String)`（错误体序列化为 JSON 字符串）。前端必须检查 `status === 'rejected'`，**不能只看 `fulfilled`**——这条对应项目自己的 `model_switch 拒绝假成功` 规则。

`ready` 事件：Python `__main__.py` 在 `RpcServer.serve()` 进入主循环前 emit `{"type":"event","event":"ready"}`，Rust 端通过 `app.listen("ready", ...)` 收到。这是**唯一**用 Tauri 事件总线做 Rust 内部协调的路径，**注意 Tauri 2 `EventId` 是 `u32` 别名**（无 `Drop`），丢弃 `let _ = ...listen(...)` 不会取消订阅，listener 一直存在。

## Tauri 命令 → RPC handler 路由

Tauri 侧只暴露 3 个 command（`src-tauri/src/lib.rs` invoke_handler）：

| Tauri command | 行为 |
|---|---|
| `start_python` | 启动 Python 子进程（idempotent：已启动返回 `Err("python already started")`） |
| `stop_python` | 杀子进程、清空状态 |
| `rpc_call(method, params)` | 走 RpcBridge 调 Python handler |

Python 14 个 handler：`rpc_handlers.py::make_handlers`：

```
ping, list_windows, get_calibration, launch_calibration_wizard,
start_run, stop_run, pause_decision,
list_trace_sessions, get_session_detail,
get_config, update_config,
get_model_services, switch_model, test_model
```

## 构建 / 启动

```bash
# 开发（前端 dev server + Tauri 自动 beforeDevCommand 拉起 vite）
cd src-tauri && cargo tauri dev

# Release（自动 beforeBuildCommand: npm --prefix ../web run build → vite build → tauri bundle）
cd src-tauri && cargo tauri build
#   产物：src-tauri/target/release/bundle/{msi,nsis,deb,...}/ChaoxingAgent_*
```

## 性能 / 安全红线（CLAUDE.md 同步）

- **不要给 vision provider 开 `enable_thinking:true` / `reasoning_effort`**（mimo-v2.5 端点开思考后 30-40s，关闭 ~7s）
- **vision `max_tokens` ≥ 3000**（低于 3000 会 finish=length 空回）
- **solver `use_response_format=true` 且 `max_tokens >= 2000`**（同样避免空回）；配 `reasoning_effort=low`
- **点击屏幕坐标前必须 `mapper.refresh()`**（`click_options` / `click_next_button` 已自动 refresh；新入口必须遵守）
- **视觉 box 必须落在截图内**（`state_machine._box_in_image` 越界即暂停）
- **`main.py` 等接口不出现提交按钮的运行时开关**（`stop_on_submit` 废弃；那是硬安全边界）

## .gitignore 约定

不入库（`5edaeb9 chore(ignore)` 立下的项目惯例）：

- `config/config.json`、`config/.env`、`config/model_services.json`（真实配置）
- `test.py`、`design-system/`、`.ui-preview/`（临时/设计稿）
- `src-tauri/target/`、`src-tauri/gen/`、`src-tauri/Cargo.lock`（Rust/Tauri 构建产物）
- `src-tauri/icons/icon.ico`（766 字节临时占位，等正式设计稿替换）
- `docs/superpowers/`（临时 plan/spec）
- `.venv/`、`__pycache__/`、`.pytest_cache/` 等环境/编译缓存
