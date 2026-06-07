# Runbook — 运维 / 故障排查 / 冒烟

> 5 分钟内找到"这个为什么没跑起来"或"这个怎么跑"的答案。

## 快速开始（5 步）

```bash
# 1. Python 侧：装依赖
uv venv
uv pip install -r requirements.txt

# 2. 初始化本地配置（首次会从 *.example 复制真实 config 到 config/）
uv run python main.py --init-config

# 3. 填 API key（编辑 config/.env；不入库）
#    VISION_API_KEY=...
#    SOLVER_API_KEY=...

# 4. 编辑 config/config.json 目标进程（详见 config/config.json.example.md）
#    target.process_name = "vivoScreen"  （或填 pid）

# 5a. 仅跑 Python（不开 Tauri 壳，调试快）：
uv run python main.py

# 5b. 跑 Tauri 桌面壳（自动 beforeDevCommand 拉 vite）：
cd src-tauri && cargo tauri dev
```

## 冒烟测试

### Python RPC 子进程

不启 Tauri 也能直接 smoke：

```bash
# 期望 stdout: {"type":"event","event":"ready",...} 然后 {"type":"response","id":1,"result":{"pong":true,...}}
printf '%s\n' '{"type":"request","id":1,"method":"ping","params":{}}' \
  | uv run python -m chaoxing_agent --rpc
```

如果只看到 `parse error` 或 hang，检查：

- Python ≥ 3.10（`python --version`）
- `chaoxing_agent/__main__.py` 在（之前缺这个文件会直接 `No module named chaoxing_agent.__main__`）
- `config/config.json` 已生成（`uv run python main.py --init-config`）

### Rust 侧编译

```bash
cd src-tauri
# 确认能过：
PATH="/d/software/Rust/rustup/toolchains/stable-x86_64-pc-windows-msvc/bin:$PATH" \
  cargo check
```

### 前端构建

```bash
cd web
npm run build     # tsc --noEmit && vite build → web/dist/
```

## 常见故障

### 启动时 5 秒后报 "python did not send ready event within 5s"

按顺序排查：

1. **Python 子进程秒退** — `python -m chaoxing_agent --rpc` 直接跑，**不要**用 Tauri，看 stderr。如果看到 `No module named chaoxing_agent.__main__`，说明 `__main__.py` 不在（之前踩过这个坑，必须存在）。
2. **subprocess EOF 后 ready 事件已被 emit 但 Rust 没收** — 看 `web/src/lib/tauri-bridge.ts` 是否有 `listen("ready", ...)` 监听；事件名是 `"ready"`（字符串，不是其他大小写）。
3. **冷启动慢** — 首次 `uv run` 会拉 .venv，慢于 5s。临时把 `python_proc.rs` 的 5s 超时调大；正式解决走 `uv sync` 预热。

### Tauri 2 `app.listen("ready", ...)` 监听不到事件

**反直觉事实**（踩坑记录）：Tauri 2.11.2 的 `EventId` 是 `pub type EventId = u32;`（见 `tauri-2.11.2/src/event/mod.rs:19`），**纯数字别名，无 `Drop` 实现**。所以 `let _ = app.listen(...)` **不会**取消订阅，listener 会一直存活到 AppHandle 销毁。不要写 `let _ = ...listen(...)` 假装"用完丢弃"——如果将来要主动取消订阅，必须绑定到变量 `let id = ...listen(...); ...; id.unlisten();`。

### `cargo tauri build` 跑通但 EXE 没图标（Windows）

`tauri.conf.json::bundle.icon` 必须包含 `.ico` 文件。当前 `icons/icon.ico` 是 766 字节的占位，正式发布前要替换成真图标（256×256 多分辨率）。`icons/icon.png` 也保留作为通用图标源。

### `cargo tauri build` 没跑前端构建 / web/dist 是空的

`tauri.conf.json` 缺 `beforeBuildCommand`。当前项目用 `npm --prefix ../web run build`（cwd-robust 形式）。如果 web/dist 已经被改动，删了重 build。

### Rust 编译失败：`error: program not found`（找不到 rustc）

rustup 多 toolchain 共存时 cargo 内部子进程找不到 `rustc`。两种解决：

```bash
# 方案 A：把目标 toolchain 的 bin 提前到 PATH
export PATH="/path/to/rustup/toolchains/stable-x86_64-pc-windows-msvc/bin:$PATH"

# 方案 B：直接调用目标 toolchain 的 cargo
/path/to/rustup/toolchains/stable-x86_64-pc-windows-msvc/bin/cargo.exe check
```

### Python 错误在 Tauri 前端被吞掉

`rpc_call` 的 Tauri 命令返回 `Result<Value, String>`。Python 侧 `RpcMessage::Error` **走 `Err` 通道**（修复 #7 后），前端必须：

```ts
const result = await invoke('rpc_call', { method, params });
// 注意：检查 status 而不是只看值
if (result instanceof Error) {
  // 真正的失败
}
```

不要假定 `result` 非空就是成功——`result.value` 可能是 `{error: {...}}` 的旧 smuggle 形态（已不再产生，但读旧代码要警惕）。

## 环境变量

| 变量 | 用途 | 加载位置 |
|---|---|---|
| `VISION_API_KEY` | 视觉模型 API key | `config/.env` → `chaoxing_agent.core.env_settings.load_env_file` |
| `SOLVER_API_KEY` | 文本模型 API key | 同上 |
| `CHAOXING_VISION_<FIELD>` | 覆盖 vision provider；`<FIELD>` ∈ `{BASE_URL, MODEL_ID, API_KEY_ENV, API_TYPE}` | 同上 |
| `CHAOXING_SOLVER_<FIELD>` | 覆盖 solver provider；同上 | 同上 |

`config.json` 的可调字段**不**通过环境变量覆盖（CLAUDE.md 写明）。

## 性能红线（详细见 CLAUDE.md）

| 项 | 红线 |
|---|---|
| vision `enable_thinking` / `reasoning_effort` | **关闭**（`vision.extra_body` 不带） |
| vision `max_tokens` | **≥ 3000** |
| solver `use_response_format` | **true** |
| solver `max_tokens` | **≥ 2000** |
| solver `reasoning_effort` | `low` |

低于上述任一阈值都会 `finish=length` 空回。

## 关键命令清单

| 命令 | 作用 |
|---|---|
| `uv run python main.py` | 启动 Python 主程序（v1 入口） |
| `uv run python main.py --init-config` | 强制从 example 覆盖 config.json / model_services.json |
| `uv run python main.py --init-env` | 重新生成 `config/.env.example` |
| `uv run python -m chaoxing_agent --rpc` | 启动 RPC 子进程（被 Tauri 调用） |
| `uv run pytest tests/` | 跑全部测试 |
| `cd src-tauri && cargo tauri dev` | Tauri 开发模式（自动跑 vite） |
| `cd src-tauri && cargo tauri build` | Tauri release 构建（自动跑 vite build + bundle） |
| `cd web && npm run build` | 仅前端构建（→ web/dist/） |
| `cd web && npm run typecheck` | 仅 TS 类型检查 |
