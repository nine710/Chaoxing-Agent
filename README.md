# ChaoxingAgent v1

Windows 本地自动化答题工具。

## 功能

- 绑定远程手机控制 / 投屏应用窗口（如 vivoScreen）
- 手动框选手机画面区域
- 视觉模型解析题目结构（题干 / 选项 / 按钮位置）
- 文本模型作答
- 自动点击选项和下一题
- 遇到交卷按钮自动停止
- 完整 trace 日志（每步截图 + JSON）

## 环境要求

- Windows 10+
- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

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

# 5. 运行
uv run python main.py
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
| `uv run python main.py` | 启动主程序（首次会自动复制本地配置） |
| `uv run python main.py --init-config` | 强制从 example 覆盖 `config.json` / `model_services.json`（不会覆盖已有 `config/.env`） |
| `uv run python main.py --init-env` | 重新生成 `config/.env.example` |

## 免责声明

本工具仅用于授权场景下的自测、题库练习、自动化 QA 或内部测试。

**严禁**用于：

- 真实考试、认证考核
- 绕过学习平台规则或反作弊系统
- 任何未授权的自动化操作

使用本工具产生的一切后果由使用者自行承担。
