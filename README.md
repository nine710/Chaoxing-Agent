# ChaoxingAgent

Windows 本地自动化答题工具 — Python 内核（截图 / 视觉 / 点击 / 状态机）+ Tauri 2 桌面壳 + React 前端。

## 两种运行方式

### A. 桌面壳（Tauri 2）— 完整体验

```bash
# 一次性：装 Python 依赖
uv venv && uv pip install -r requirements.txt

# 初始化本地配置
uv run python main.py --init-config

# 起桌面壳（自动 beforeDevCommand 拉 vite dev server）
cd src-tauri && cargo tauri dev
```

### B. 纯 Python（无 UI，调试快）

```bash
uv venv && uv pip install -r requirements.txt
uv run python main.py --init-config
uv run python main.py
```

## 功能

- 手动框选手机画面区域（标定向导）
- 视觉模型解析题目结构（题干 / 选项 / 按钮位置）
- 文本模型作答
- 自动点击选项和下一题
- 遇到交卷按钮自动停止
- 完整 trace 日志（每步截图 + JSON）
- Tauri 2 桌面壳：原生窗口 + 配置 / 监控 / 日志 / 历史 / 标定 5 个 tab

## 环境要求

- Windows 10+（用 `pywin32` 操控窗口和点击）
- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- Rust toolchain（仅 Tauri 壳需要；见 `src-tauri/Cargo.toml::rust-version`）
- Node.js ≥ 18（仅前端 build 需要）

## 快速开始

```bash
# 1. 进入项目目录
cd ChaoxingAgent

# 2. 创建虚拟环境并安装依赖
uv venv
uv pip install -r requirements.txt

# 3. 准备本地配置（首次运行会自动从 *.example 复制生成）
uv run python main.py --init-config   # 强制从 example 覆盖 config.json / model_services.json
uv run python main.py --init-env      # 重新生成 config/.env.example

# 4. 编辑本地配置（真实文件被 .gitignore 排除，不入库）
#    config/config.json         运行时参数（target / viewport / timing / ...）
#    config/model_services.json 视觉 + 文本模型服务商配置
#    config/.env                模型 API key（不入库）

# 5a. 仅跑 Python（不开 UI）
uv run python main.py

# 5b. 跑 Tauri 桌面壳（需要先有 Rust + Node）
cd src-tauri && cargo tauri dev
```

## 配置说明

- 所有可调模板都以 `*.example` 形式入库，真实配置由 `.gitignore` 排除
- 模板字段含义放在 `config/*.example.md` 中
- `config/.env` **仅**承载模型服务相关项：
  - `VISION_API_KEY` / `SOLVER_API_KEY`（由 `model_services.json` 的 `api_key_env` 指向）
  - 可选覆盖：`CHAOXING_VISION_<FIELD>` / `CHAOXING_SOLVER_<FIELD>`，FIELD 可为 `BASE_URL` / `MODEL_ID` / `API_KEY_ENV` / `API_TYPE`
- 其它运行时参数（`config.json`）**不**通过 `.env` 覆盖

## 模型服务

视觉和文本模型各使用一个 OpenAI 兼容 provider（任何 `/v1/chat/completions` 端点都可用：OpenAI、Azure、自建网关、自部署 LLM...）。

```json
{
  "vision": { "api_type": "openai", "base_url": "...", "api_key_env": "VISION_API_KEY", "model_id": "..." },
  "solver": { "api_type": "openai", "base_url": "...", "api_key_env": "SOLVER_API_KEY", "model_id": "..." }
}
```

完整字段说明见 `config/config.json.example.md` 和 `config/model_services.json.example`。

## CLI 命令

| 命令 | 作用 |
|------|------|
| `uv run python main.py` | 启动 Python 主程序（首次会自动复制本地配置） |
| `uv run python main.py --init-config` | 强制从 example 覆盖 `config.json` / `model_services.json`（不会覆盖已有 `config/.env`） |
| `uv run python main.py --init-env` | 重新生成 `config/.env.example` |
| `uv run python -m chaoxing_agent --rpc` | 启动 RPC 子进程（被 Tauri 壳调用） |
| `cd src-tauri && cargo tauri dev` | Tauri 桌面壳开发模式（自动跑 vite dev） |
| `cd src-tauri && cargo tauri build` | Tauri release 构建（自动跑 vite build + bundle） |

## 架构 / 运维

- 整体设计 + NDJSON 协议：见 `docs/architecture.md`
- 故障排查 / 冒烟测试：见 `docs/runbook.md`
- 外部集成（写新 host 接入 RPC）：见 `docs/integration-guide.md`

## 免责声明

本工具仅用于授权场景下的自测、题库练习、自动化 QA 或内部测试。

**严禁**用于：

- 真实考试、认证考核
- 绕过学习平台规则或反作弊系统
- 任何未授权的自动化操作

使用本工具产生的一切后果由使用者自行承担。
