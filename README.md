# ChaoxingAgent v1

Windows 本地自动化答题工具。

## 功能

- 绑定远程手机控制/投屏应用窗口
- 手动框选手机画面区域
- 视觉模型解析题目结构（题干/选项/按钮）
- 文本模型作答
- 自动点击选项和下一题
- 遇到交卷按钮自动停止
- 完整 trace 日志

## 环境要求

- Windows 10+
- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

## 快速开始

```bash
# 1. 进入项目
cd ChaoxingAgent

# 2. 创建虚拟环境并安装依赖
uv venv
uv pip install -r requirements.txt

# 3. 配置模型服务
#    编辑 config/model_services.json 设置你的 API 端点
#    设置环境变量:
#      set VISION_API_KEY=your-key
#      set SOLVER_API_KEY=your-key

# 4. 运行
uv run python main.py
```

## 项目结构

```text
ChaoxingAgent/
├── main.py                  # 入口
├── config/                  # 配置文件
├── core/                    # 核心逻辑（截图/坐标/点击/检测/状态机/trace）
├── models/                  # 模型服务层（配置/客户端/解析/作答）
├── schemas/                 # Pydantic 数据校验模型
├── prompts/                 # 模型提示词模板
└── trace/                   # 运行时 trace 日志
```

## 使用限制

仅用于授权的自测、题库练习、自动化 QA 或内部测试。
不用于真实考试、绕过平台规则、反作弊或未授权自动化。

## License

Internal use only.
