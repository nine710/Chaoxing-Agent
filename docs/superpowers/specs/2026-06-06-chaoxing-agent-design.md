# ChaoxingAgent v1 设计文档

> 版本: v1.0
> 日期: 2026-06-06
> 项目路径: `D:\mytmp\ChaoxingAgent`
> 技术栈: Python 3.10+ / pywin32 / tkinter / pydantic v2 / OpenCV / requests

---

## 1. 项目概述与约束

### 1.1 项目定位

ChaoxingAgent 是一个 **Windows 本地自动化程序**，功能专一：

> 用户打开远程手机控制/投屏应用 → 手动框选手机画面区域 → 程序对该区域循环截图 → 视觉模型解析题目结构 → 文本模型作答 → 程序点击选项和下一题 → 遇到交卷按钮停止。

不是通用 Computer Use、不是 MCP Server、不是 ADB 控制。

### 1.2 使用范围

仅用于 **授权的自测、题库练习、自动化 QA 或内部测试**。不允许用于真实考试、绕过平台规则、反作弊或未授权自动化。

### 1.3 核心原则

```
视觉模型   →  看页面、提取结构（题干/选项/按钮矩形）
文本模型   →  根据题干和选项判断答案
本地程序   →  截图、点击、状态机控制、页面变化检测
```

| 不做的事 | 原因 |
|----------|------|
| 视觉模型不负责答题 | 职责分离，减少幻觉 |
| 文本模型不负责看页面 | 只处理结构化文本输入 |
| LLM 不直接控制鼠标 | 坐标转换由程序完成 |
| 不自动交卷 | 安全边界 |
| 不自动处理弹窗 | 需要用户判断 |
| 不做选中状态检测 | v1 用页面变化替代 |

### 1.4 硬约束（不可配置，不可关闭）

| # | 约束 | 触发条件 |
|---|------|---------|
| 1 | 绝不自动点击交卷按钮 | `page_state == "submit"` 或 `buttons.submit.visible == True` |
| 2 | 坐标必须经映射层转换 | 所有点击操作 |
| 3 | LLM 返回截图内像素坐标 | 视觉模型 prompt 强制要求 |
| 4 | 弹窗暂停 | `popup.visible == True` |
| 5 | 窗口尺寸变化暂停 | 变化超 5% |
| 6 | 连续异常停止 | 连续 ≥ 3 次 |
| 7 | API Key 只读环境变量 | 不写入任何文件 |

---

## 2. 分层架构

### 2.1 四层模型

```
┌──────────────────────────────────────────────────────────────┐
│                    表示层 (Presentation)                      │
│                                                              │
│  main.py                 CLI 交互入口，启动/暂停/恢复          │
│  window_selector.py      进程/PID → 窗口列表 → 用户选择       │
│  viewport_selector.py    客户区截图 → tkinter ROI 框选        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                   核心逻辑层 (Core Logic)                      │
│                                                              │
│  state_machine.py         主循环编排，步骤串联                 │
│  screen_capture.py        窗口截图（含存活/尺寸检查）          │
│  coordinate_mapper.py     手机截图坐标 → 屏幕坐标              │
│  click_executor.py        鼠标点击（含多选间隔时序）           │
│  page_change_detector.py  图像差异检测（裁剪→灰度→比例）      │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                  模型服务层 (Model Service)                    │
│                                                              │
│  model_config.py          配置读取 + 客户端工厂                │
│  vision_parser.py         视觉请求构造 → 调用 → JSON 校验      │
│  text_solver.py           文本请求构造 → 调用 → JSON 校验      │
│  openai_client.py         POST /chat/completions              │
│  google_client.py         POST :generateContent                │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                      数据层 (Data)                            │
│                                                              │
│  config.json              运行时配置（target/viewport/timing）  │
│  model_services.json      模型服务商注册 + selected            │
│  trace_logger.py          每步截图 + JSON 落盘                 │
│  schemas/vision_schema.py 视觉输出 Pydantic 校验模型           │
│  schemas/solver_schema.py 文本输出 Pydantic 校验模型           │
│  prompts/                 视觉/文本 system prompt 模板          │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 层间依赖规则

```
表示层 ──调用──→ 核心逻辑层 ──调用──→ 模型服务层 ──调用──→ LLM API
  │                 │                    │
  └───────→ 数据层 ←─────────────────────┘
        (配置读写)            (trace 落盘 + prompt 读取)
```

- 上层可调用下层，下层绝不引用上层
- 核心逻辑层通过 `model_config.py` 间接获取客户端，不直接依赖 `openai_client` 或 `google_client`
- 坐标映射只在核心逻辑层完成，表示层和模型服务层不涉及坐标运算
- `config.json` 和 `model_services.json` 是唯一的状态持久化入口

### 2.3 模块清单与对外暴露

| 层 | 模块 | 对外暴露的核心接口 |
|----|------|-------------------|
| 表示层 | `main.py` | 入口，无对外接口 |
| 表示层 | `window_selector.py` | `select(user_input: str) -> WindowInfo` |
| 表示层 | `viewport_selector.py` | `select(window_info: WindowInfo) -> ViewportInfo` |
| 核心层 | `state_machine.py` | `StateMachine.run() -> None` |
| 核心层 | `screen_capture.py` | `capture_client_area(hwnd) -> Image`<br>`capture_phone_screen(hwnd, viewport) -> Image`<br>`check_window_alive(hwnd) -> bool`<br>`check_window_size_unchanged(hwnd, expected) -> bool` |
| 核心层 | `coordinate_mapper.py` | `CoordinateMapper(hwnd, viewport)`<br>`.image_to_screen(x,y) -> (int,int)`<br>`.box_center_screen(box) -> (int,int)` |
| 核心层 | `click_executor.py` | `click_at(x, y)`<br>`click_options(answers, options, mapper, timing)`<br>`click_next_button(box, mapper, timing)` |
| 核心层 | `page_change_detector.py` | `detect(before, after, region, threshold) -> bool`<br>`wait_for_change(before, capture_fn, config) -> (bool, Image\|None)` |
| 模型层 | `model_config.py` | `load_model_services() -> dict`<br>`get_vision_config(services) -> ModelConfig`<br>`get_solver_config(services) -> ModelConfig` |
| 模型层 | `vision_parser.py` | `parse(image: Image, config: ModelConfig) -> VisionResult` |
| 模型层 | `text_solver.py` | `solve(qtype, question, options, config) -> SolverResult` |
| 模型层 | `openai_client.py` | `OpenAIClient(config).chat(messages) -> str` |
| 模型层 | `google_client.py` | `GoogleClient(config).chat(messages) -> str` |
| 数据层 | `trace_logger.py` | `TraceLogger(trace_dir).save_step(step_data: dict)` |
| 数据层 | `schemas/` | Pydantic model 定义（`VisionResult`, `SolverResult`） |
| 数据层 | `prompts/` | `vision_prompt.txt`, `solver_prompt.txt` |

---

## 3. 层间接口规范

### 3.1 表示层 → 核心逻辑层

```
main.py 启动流程:
  ① window_selector.select(user_input) → WindowInfo
  ② viewport_selector.select(WindowInfo) → ViewportInfo
  ③ 将 WindowInfo + ViewportInfo 写入 config.json
  ④ state_machine.StateMachine(config_dict, model_services_dict).run()

表示层不直接调用核心层的其他模块（screen_capture 除外，供 viewport_selector 截图用）。
```

### 3.2 核心逻辑层 → 模型服务层

```
vision_parser.parse(
    image: PIL.Image,            # RGB 手机画面截图
    config: ModelConfig          # {api_type, base_url, api_key, model_id}
) -> VisionResult                 # Pydantic model
  异常: JSONParseError | VisionValidationError

text_solver.solve(
    question_type: str,          # "single_choice" / "multiple_choice" / ...
    question_text: str,          # 题干
    options: dict[str, str],     # {"A": "...", "B": "...", ...}
    config: ModelConfig
) -> SolverResult                # Pydantic model
  异常: JSONParseError | SolverValidationError
```

核心逻辑层不 import 具体客户端类，只通过 `model_config.py` 获取 `ModelConfig`，由 `vision_parser` / `text_solver` 内部根据 `api_type` 选择 `OpenAIClient` 或 `GoogleClient`。

### 3.3 核心逻辑层 → 数据层

```
trace_logger.TraceLogger(trace_dir: str)
  .save_step(step_data: dict)     # 写截图 + JSON 到 trace/ 目录

配置文件:
  - 启动时一次性 load_model_services() → dict
  - 运行时通过 dict 传递，不反复读文件
  - 标定完成后一次性写 config.json，运行时不再写
```

### 3.4 关键数据结构

```python
# === 表示层 ===

WindowInfo:
    hwnd: int
    pid: int
    process_name: str
    window_title: str
    client_rect: (left, top, right, bottom)    # 客户区屏幕绝对坐标
    screen_rect: (left, top, right, bottom)    # 窗口整体屏幕坐标
    width: int                                   # client_rect 宽度
    height: int                                  # client_rect 高度

ViewportInfo:
    x: int                                      # 相对客户区左上角偏移
    y: int
    width: int
    height: int
    ratio_x: float                              # x / client_width
    ratio_y: float                              # y / client_height
    ratio_w: float                              # width / client_width
    ratio_h: float                              # height / client_height

# === 模型层 ===

ModelConfig:
    api_type: str                               # "openai" | "google"
    base_url: str
    api_key: str                                # 已从环境变量读取
    model_id: str

# === 视觉结果 ===

VisionResult:
    page_state: "question" | "submit" | "popup" |
                "loading" | "finished" | "unknown"
    question_type: "single_choice" | "multiple_choice" |
                   "true_false" | "fill_blank" | "unknown"
    question_text: str
    options: list[VisionOption]
    buttons: VisionButtons
    popup: VisionPopup
    confidence: VisionConfidence

    VisionOption:
        key: str                                # "A" / "B" / "C" / "D"
        text: str
        box: [x1, y1, x2, y2]                  # 手机截图内像素坐标

    VisionButtons:
        previous: VisionButton
        next: VisionButton
        submit: VisionButton

    VisionButton:
        visible: bool
        text: str
        box: [x1, y1, x2, y2] | None

    VisionPopup:
        visible: bool
        text: str
        buttons: list                            # v1 不处理

    VisionConfidence:
        text: float                              # 文字识别置信度
        layout: float                            # 布局识别置信度

# === 文本结果 ===

SolverResult:
    question_type: str
    answer: list[str]                            # 必须是数组
    confidence: float
    reason: str

# === 状态机 ===

StepResult:
    should_stop: bool
    stop_reason: str                             # "submit" | "finished" | "error" | "max_steps"
    step_data: dict | None                       # trace 数据
```

---

## 4. 关键跨层机制

### 4.1 坐标映射

这是整个系统最关键的跨层机制，贯穿截图、视觉解析、点击三个环节。

```
坐标系层级:

  Windows 屏幕绝对坐标 ─── 用户看得见的鼠标位置
        │
        ├─ client_rect: 目标窗口客户区在屏幕上的位置
        │       │
        │       ├─ phone_viewport: 手机画面在客户区内的偏移
        │       │       │
        │       │       └─ 手机截图像素坐标 ─── LLM 返回的 box
        │       │
        │       └─ (工具栏、窗口边框等，不关心)
        │
        └─ (桌面其他区域，不关心)

转换公式:

  已知:
    client_left, client_top  = client_rect 左上角 (屏幕坐标)
    viewport_x, viewport_y  = phone_viewport 相对客户区的偏移 (像素)

  则:
    phone_left = client_left + viewport_x
    phone_top  = client_top  + viewport_y

  手机截图像素 (ix, iy) → 屏幕坐标 (sx, sy):
    sx = phone_left + ix
    sy = phone_top  + iy

  box [x1,y1,x2,y2] → 屏幕中心点击点:
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    screen_click = (phone_left + cx, phone_top + cy)
```

**硬规则**: LLM 只返回手机截图内像素坐标，程序负责转为屏幕坐标。任何情况下都不允许 LLM 返回的坐标直接用于鼠标点击。

### 4.2 页面变化检测

完全由程序完成，不调用 LLM。

```
流程:
  ① 点击下一题前 → capture_phone_screen() → before_img
  ② 点击下一题 → sleep(0.5s)
  ③ capture_phone_screen() → after_img

检测算法:
  ① 按 compare_region 裁剪:
     crop_box = (0, h*0.08, w, h*0.75)    # 题目区域，排除状态栏和底部按钮
  ② before_crop, after_crop → .convert('L') → 灰度
  ③ resize((200, 200)) → 减少光照/微小位移干扰
  ④ np.abs(before_arr - after_arr) / 255.0 → diff
  ⑤ changed_ratio = np.mean(diff > 0.1)
  ⑥ changed_ratio > page_change_pixel_ratio(默认0.03) → True

未变化处理:
  ① sleep(extra_wait_if_page_not_changed) → 0.5s
  ② 重新截图 → 再检测
  ③ 仍不变 → sleep + 重试，直到 max_page_change_wait(3s)
  ④ 超时 → 返回 False → 上层暂停
```

### 4.3 安全硬编码检查点

这些检查在 `state_machine.py` 的 `process_one_step()` 中硬编码，不依赖配置文件，不可跳过。

```
Checkpoint 1 — 交卷检测 (在视觉解析后立即执行):
  if vision_result.page_state == "submit":
      return StepResult(should_stop=True, stop_reason="submit")
  if vision_result.buttons.submit.visible == True:
      return StepResult(should_stop=True, stop_reason="submit_button_visible")

Checkpoint 2 — 弹窗检测:
  if vision_result.popup.visible and config.runtime.pause_on_popup:
      pause("检测到弹窗，请手动处理")

Checkpoint 3 — 未知页面:
  if vision_result.page_state == "unknown" and config.runtime.pause_on_unknown:
      pause("无法识别页面状态")

Checkpoint 4 — 答案校验 (在文本模型返回后):
  if solver_result.confidence < config.thresholds.solver_confidence:
      pause(f"文本模型置信度过低: {solver_result.confidence}")
  for answer in solver_result.answer:
      if answer not in [opt.key for opt in vision_result.options]:
          pause(f"答案 '{answer}' 无法映射到选项")

Checkpoint 5 — 窗口存活:
  if not check_window_alive(hwnd):
      return StepResult(should_stop=True, stop_reason="window_gone")

Checkpoint 6 — 窗口尺寸:
  if not check_window_size_unchanged(hwnd, expected_client_rect):
      pause("窗口尺寸已变化，请重新标定手机画面区域")

Checkpoint 7 — 坐标映射强制:
  # 所有点击必须走 coordinate_mapper，禁止直接使用 LLM 返回坐标
  # 实现方式: click_executor 只接受 (x, y) 屏幕坐标 +
  #           CoordinateMapper 实例，不接受 box 直接点击
```

---

## 5. 状态机与循环控制流

### 5.1 顶层生命周期

```
         ┌─────────┐
         │  START  │
         └────┬────┘
              │
    ┌─────────▼──────────┐
    │  窗口绑定与标定     │  ← window_selector + viewport_selector
    │  填充 config.json  │
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │  初始化             │  ← 加载配置、创建 CoordinateMapper、
    │                     │     创建 Vision/Solver 客户端、创建 TraceLogger
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │  LOOP (per step)   │  ← process_one_step()
    │  step = 1 .. max   │
    └────┬──────────┬────┘
         │          │
    should_stop    should_stop
      = True         = False
         │          │
    ┌────▼───┐      └──→ 回到 LOOP
    │  STOP  │
    └────────┘
```

### 5.2 单步流程 `process_one_step()`

```
 ① check_window_alive(hwnd)
    └─ 不存活 → StepResult(stop, "window_gone")

 ② check_window_size_unchanged(hwnd, expected)
    └─ 变化 > 5% → Pause("窗口尺寸变化")

 ③ screenshot = capture_phone_screen(hwnd, viewport)
    └─ 截图保存到内存 (PIL.Image)，暂不落盘

 ④ vision = vision_parser.parse(screenshot, vision_config)
    └─ 异常 → Pause("视觉模型返回异常")

 ⑤ GUARD: 检查 page_state
    ├─ "submit" 或 submit.visible → StepResult(stop, "submit")
    ├─ "popup"   → Pause("检测到弹窗")
    ├─ "unknown" → Pause("无法识别页面")
    └─ "loading" → 等待 1s 后重新进入步骤 ③（最多重试 3 次）
    └─ "question" → 继续

 ⑥ solver = text_solver.solve(
        vision.question_type,
        vision.question_text,
        {opt.key: opt.text for opt in vision.options},
        solver_config
    )

 ⑦ GUARD: 校验答案
    ├─ confidence < threshold → Pause("置信度过低")
    ├─ answer 无法映射到 options → Pause("答案无效")
    ├─ question_type 冲突 → Pause("类型不一致")
    └─ 通过 → 继续

 ⑧ click_executor.click_options(solver.answer, vision.options, mapper, timing)
    - 单选: 点击 1 次
    - 多选: 依次点击，间隔 timing.between_multi_select_clicks(0.2s)

 ⑨ before_img = capture_phone_screen(hwnd, viewport)

 ⑩ click_executor.click_next_button(vision.buttons.next.box, mapper, timing)
    - 点击前等待 timing.before_click_next(0.2s)
    - 执行点击
    - 点击后等待 timing.after_click_next(0.5s)

 ⑪ changed, after_img = page_change_detector.wait_for_change(
        before_img, capture_fn, config
    )
    └─ 未变化 → Pause("页面未跳转")

 ⑫ trace_logger.save_step(step_data)
    → StepResult(stop=False, step_data=step_data)
```

### 5.3 暂停机制

```
暂停 ≠ 停止。暂停是可控的等待用户指令。

暂停时程序行为:
  ① 当前截图立即保存到 trace/ 目录
  ② 视觉模型 JSON 保存
  ③ 文本模型 JSON 保存
  ④ 错误原因打印到控制台
  ⑤ 显示提示: "按 Enter 重试当前步骤 / 输入 'skip' 跳过 / 输入 'quit' 退出"
  ⑥ 用户选择后:
     - Enter → 重新执行当前 step（不增加 step 计数）
     - skip  → 增加 step 计数，进入下一轮（可能再次在本步骤暂停）
     - quit  → 最终停止，保存所有 trace
```

### 5.4 停止机制

```
停止 = 不可恢复，保存所有 trace 并退出循环。

触发条件:
  ① page_state == "submit" 或 submit.visible
  ② page_state == "finished"
  ③ 连续异常次数 ≥ 3
  ④ step 达到 max_steps
  ⑤ 窗口不存在
  ⑥ 用户输入 'quit'

停止时行为:
  ① 保存当前截图和模型输出到 trace
  ② 打印停止原因
  ③ 打印 trace 目录路径
  ④ 正常退出 (sys.exit(0))，不抛异常
```

---

## 6. 配置文件设计

### 6.1 config.json

```json
{
  "target": {
    "process_name": "vivoScreen.exe",
    "pid": 12724,
    "selected_hwnd": 198742,
    "window_title": "vivo投屏",
    "client_rect": [0, 0, 520, 960]
  },
  "viewport": {
    "lock_window_size_after_calibration": true,
    "phone_viewport_in_client": {
      "x": 42,
      "y": 76,
      "width": 420,
      "height": 910
    },
    "phone_viewport_ratio": {
      "x": 0.048,
      "y": 0.072,
      "width": 0.477,
      "height": 0.864
    }
  },
  "timing": {
    "between_multi_select_clicks": 0.2,
    "before_click_next": 0.2,
    "after_click_next": 0.5,
    "extra_wait_if_page_not_changed": 0.5,
    "max_page_change_wait": 3.0
  },
  "thresholds": {
    "vision_text_confidence": 0.75,
    "vision_layout_confidence": 0.75,
    "solver_confidence": 0.70,
    "page_change_pixel_ratio": 0.03,
    "window_size_change_ratio": 0.05
  },
  "page_change": {
    "compare_region_ratio": {
      "x1": 0.0,
      "y1": 0.08,
      "x2": 1.0,
      "y2": 0.75
    },
    "compare_resize": [200, 200]
  },
  "runtime": {
    "max_steps": 200,
    "stop_on_submit": true,
    "pause_on_popup": true,
    "pause_on_unknown": true,
    "save_trace": true,
    "loading_retry_max": 3,
    "loading_retry_delay": 1.0,
    "max_consecutive_errors": 3
  }
}
```

**字段职责:**

| 字段 | 职责 | 谁写入 | 谁读取 |
|------|------|-------|--------|
| `target.*` | 窗口绑定信息 | `window_selector.py` | `state_machine.py`, `screen_capture.py`, `coordinate_mapper.py` |
| `viewport.*` | 手机画面映射 | `viewport_selector.py` | `screen_capture.py`, `coordinate_mapper.py` |
| `timing.*` | 点击/等待时序 | 用户可手动调整 | `click_executor.py` |
| `thresholds.*` | 校验阈值 | 用户可手动调整 | `state_machine.py` (guard 逻辑) |
| `page_change.*` | 变化检测参数 | 用户可手动调整 | `page_change_detector.py` |
| `runtime.*` | 运行策略 | 用户可手动调整 | `state_machine.py` |

### 6.2 model_services.json

```json
{
  "model_services": {
    "vision": {
      "1": {
        "name": "OpenAI Compatible Vision",
        "api_type": "openai",
        "base_url": "https://your-endpoint/v1",
        "api_key_env": "VISION_API_KEY",
        "model_id": "your-vision-model",
        "supports_image": true
      },
      "2": {
        "name": "Google Gemini Vision",
        "api_type": "google",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key_env": "GOOGLE_API_KEY",
        "model_id": "gemini-2.5-flash",
        "supports_image": true
      },
      "3": {
        "name": "Local Vision",
        "api_type": "openai",
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key_env": "LOCAL_VISION_API_KEY",
        "model_id": "local-vision",
        "supports_image": true
      }
    },
    "solver": {
      "1": {
        "name": "OpenAI Compatible Solver",
        "api_type": "openai",
        "base_url": "https://your-endpoint/v1",
        "api_key_env": "SOLVER_API_KEY",
        "model_id": "your-text-model",
        "supports_image": false
      },
      "2": {
        "name": "Google Gemini Solver",
        "api_type": "google",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key_env": "GOOGLE_API_KEY",
        "model_id": "gemini-2.5-flash",
        "supports_image": false
      },
      "3": {
        "name": "Local Solver",
        "api_type": "openai",
        "base_url": "http://127.0.0.1:8001/v1",
        "api_key_env": "LOCAL_SOLVER_API_KEY",
        "model_id": "local-solver",
        "supports_image": false
      }
    }
  },
  "selected": {
    "vision_model": "1",
    "solver_model": "1"
  }
}
```

**设计要点:**

- `api_key_env` 指定环境变量名，程序通过 `os.environ[api_key_env]` 读取
- `api_type` 决定使用 `OpenAIClient` 还是 `GoogleClient`
- `selected.vision_model` 和 `selected.solver_model` 独立选择，两者可以是同一个服务商
- vision 的 `supports_image` 必须为 `true`，solver 的为 `false`

---

## 7. 异常分类与处理策略

### 7.1 三级异常模型

```
                    ChaoxingError (基类)
                           │
           ┌───────────────┼───────────────┐
           │               │               │
  RecoverableError   PauseRequiredError   FatalStopError
  (自动重试)          (暂停等用户)         (停止退出)
```

| 级别 | 父类 | 行为 | 示例 |
|------|------|------|------|
| 可恢复 | `RecoverableError` | 记录日志 → 重试当前操作 → 仍失败则升级为 Pause | 模型返回非 JSON（可尝试正则提取）、网络超时 |
| 需暂停 | `PauseRequiredError` | 保存现场 → 通知用户 → 等待指令 | confidence < 阈值、答案无法映射、页面未变化、弹窗 |
| 致命停止 | `FatalStopError` | 保存所有 trace → 通知用户 → 退出 | 窗口关闭、连续 3 次异常、交卷按钮、达到 max_steps |

### 7.2 异常触发映射表

```
找不到进程          → FatalStopError
找不到可见窗口      → FatalStopError
窗口被关闭          → FatalStopError
窗口尺寸变化 > 5%   → PauseRequiredError  (要求重新标定)
API Key 未设置      → FatalStopError

=== 模型调用阶段 ===
视觉模型 HTTP 错误  → RecoverableError   (重试最多 3 次)
视觉返回非 JSON     → RecoverableError   (正则提取，失败则 Pause)
视觉 page_state=unknown → PauseRequiredError
视觉 confidence < threshold → PauseRequiredError
视觉识别不到选项    → PauseRequiredError
视觉识别不到下一题  → PauseRequiredError
视觉识别到交卷按钮  → FatalStopError
视觉识别到弹窗      → PauseRequiredError

文本模型 HTTP 错误  → RecoverableError   (重试最多 3 次)
文本返回非 JSON     → RecoverableError   (正则提取，失败则 Pause)
文本 confidence < threshold → PauseRequiredError
文本答案无法映射    → PauseRequiredError
文本 question_type 冲突 → PauseRequiredError

=== 点击与检测阶段 ===
点击下一题后页面未变 → PauseRequiredError

=== 综合 ===
连续异常 ≥ 3       → FatalStopError
```

### 7.3 错误恢复流程

```
RecoverableError 发生时:
  ① 错误计数 +1
  ② 打印警告: "[WARN] {错误描述}，正在重试 (第 {n} 次)"
  ③ sleep(1s)
  ④ 重试操作

重试 3 次后仍失败:
   → 升级为 PauseRequiredError

PauseRequiredError 发生时:
  ① 错误计数不变（这是预期内的暂停，不是异常）
  ② 保存 screenshot、vision_json、solver_json、error_reason 到 trace
  ③ 打印暂停原因和当前状态
  ④ 用户交互: Enter 重试 / 'skip' 跳过 / 'quit' 退出

FatalStopError 发生时:
  ① 错误计数不重要，直接进入停止流程
  ② 调用 trace_logger 保存当前 step 数据
  ③ 打印停止原因
  ④ sys.exit(0)
```

---

## 8. Trace 与可观测性

### 8.1 日志分层

```
控制台输出 (stdout/stderr):
  [INFO]  关键步骤进度 (step N, page_state, answer, click result)
  [WARN]  可恢复异常、重试
  [ERROR] 暂停原因、致命错误
  [DEBUG] 详细坐标、图像差异数值

Trace 目录 (trace/):
  每步:
    step_NNN.png    — 原始手机画面截图
    step_NNN.json   — 结构化 trace entry
```

### 8.2 Trace JSON 结构

```json
{
  "step": 12,
  "timestamp": "2026-06-06T12:00:00.000000",
  "screenshot": "trace/step_012.png",
  "page_state": "question",
  "question_type": "multiple_choice",
  "question": "题干文本",
  "options": {
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D"
  },
  "vision_confidence": {
    "text": 0.91,
    "layout": 0.93
  },
  "vision_raw_json": { "...": "视觉模型完整返回" },
  "solver_answer": ["A", "D"],
  "solver_confidence": 0.82,
  "solver_reason": "简短理由",
  "solver_raw_json": { "...": "文本模型完整返回" },
  "clicked_options": [
    {
      "key": "A",
      "box": [80, 520, 960, 620],
      "image_center": [520, 570],
      "screen_center": [820, 760]
    },
    {
      "key": "D",
      "box": [80, 910, 960, 1010],
      "image_center": [520, 960],
      "screen_center": [820, 1150]
    }
  ],
  "next_button": {
    "box": [700, 1720, 1000, 1810],
    "image_center": [850, 1765],
    "screen_center": [1150, 1955]
  },
  "page_changed": true,
  "page_change_ratio": 0.42,
  "error": null
}
```

### 8.3 Trace 目录结构

```
trace/
├── session_20260606_120000/        # 按启动时间命名
│   ├── step_001.png
│   ├── step_001.json
│   ├── step_002.png
│   ├── step_002.json
│   ├── ...
│   └── step_045.png
│   └── step_045.json
└── session_20260606_153000/
    └── ...
```

每次运行创建新的 session 子目录，避免覆盖历史 trace。

### 8.4 异常暂停时的额外保存

暂停时除正常 trace 外，额外保存：

```
trace/session_xxx/pause_step_012/
├── screenshot_at_pause.png
├── vision_result.json
├── solver_result.json
└── pause_reason.txt                # 纯文本，描述暂停原因
```

---

## 9. 项目文件树

```
ChaoxingAgent/
├── main.py                          # 入口
├── config/
│   ├── config.json                  # 运行时配置
│   └── model_services.json          # 模型服务商注册表
├── core/
│   ├── __init__.py
│   ├── window_selector.py           # Step 1
│   ├── viewport_selector.py         # Step 2
│   ├── screen_capture.py            # Step 3
│   ├── coordinate_mapper.py         # Step 3
│   ├── click_executor.py            # Step 6
│   ├── page_change_detector.py      # Step 7
│   ├── state_machine.py             # Step 8
│   └── trace_logger.py             # Step 9
├── models/
│   ├── __init__.py
│   ├── model_config.py
│   ├── base_client.py
│   ├── openai_client.py
│   ├── google_client.py
│   ├── vision_parser.py
│   └── text_solver.py
├── schemas/
│   ├── __init__.py
│   ├── vision_schema.py
│   └── solver_schema.py
├── prompts/
│   ├── vision_prompt.txt
│   └── solver_prompt.txt
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-06-chaoxing-agent-design.md  ← 本文件
├── trace/                           # 运行时创建
├── requirements.txt
├── pyproject.toml                   # uv 项目配置
└── README.md
```

### 9.1 uv 项目管理

```toml
# pyproject.toml
[project]
name = "chaoxing-agent"
version = "0.1.0"
description = "Windows 本地自动化答题工具 - 视觉模型解析 + 文本模型作答 + 本地点击控制"
requires-python = ">=3.10"
dependencies = [
    "pywin32>=306",
    "psutil>=5.9.0",
    "Pillow>=10.0.0",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0",
    "requests>=2.31.0",
    "pydantic>=2.0.0",
]

[tool.uv]
dev-dependencies = []
```

使用方式:
```bash
uv venv                    # 创建虚拟环境
uv pip install -r requirements.txt   # 安装依赖 (或 uv sync)
uv run python main.py      # 运行
```

---

## 10. 端到端验收标准

### 10.1 功能验收清单

| # | 验收项 | 验证方式 |
|---|--------|---------|
| 1 | 用户输入 PID 或进程名绑定窗口 | 用本地任意窗口（记事本）测试 |
| 2 | 多窗口时交互选择 | 打开多个窗口测试 |
| 3 | 手动框选手机画面区域 | 用任意窗口模拟 |
| 4 | 每轮只截取手机画面区域 | 检查截图尺寸和内容 |
| 5 | 视觉模型返回题干、选项、按钮矩形 | 检查 VisionResult JSON |
| 6 | 文本模型返回答案数组 | 检查 SolverResult JSON |
| 7 | 点击选项中心点 | 观察鼠标落点 |
| 8 | 多选题每个选项间隔 0.2s | 计时验证 |
| 9 | 点击下一题前等 0.2s，后等 0.5s | 计时验证 |
| 10 | 页面变化检测由程序完成 | 不在该段代码中调用任何 LLM API |
| 11 | v1 不单独检测选中状态 | 代码审查确认 |
| 12 | 交卷按钮 → 停止 | 用模拟 vision 结果测试 |
| 13 | 异常暂停 | 关闭目标窗口测试 |
| 14 | trace 日志完整 | 检查 trace 目录 |
| 15 | openai + google 两种 api_type 可切换 | 修改 selected 后重启验证 |

### 10.2 安全边界验收

| # | 验收项 | 验证方式 |
|---|--------|---------|
| 1 | 交卷按钮绝不自动点击 | 代码审查: submit.visible 路径 |
| 2 | 坐标必经映射层 | 代码审查: click_executor 不接受裸 box |
| 3 | LLM 不返回屏幕坐标 | vision_prompt 审查 |
| 4 | API Key 不在文件系统中 | 代码审查 + config 文件审查 |
| 5 | 弹窗暂停 | 模拟 popup.visible=True |

---

## 附录 A: 视觉模型提示词 (中文)

```
你正在解析一张手机屏幕截图。
这张图只包含手机画面，不包含 Windows 桌面。
请提取当前页面结构，用严格 JSON 返回。

所有矩形坐标必须基于当前截图的像素坐标 (0,0 是图片左上角)。
不要返回屏幕绝对坐标。

JSON 格式必须包含以下字段:
{
  "page_state": "question|submit|popup|loading|finished|unknown",
  "question_type": "single_choice|multiple_choice|true_false|fill_blank|unknown",
  "question_text": "题干文本",
  "options": [
    {"key": "A", "text": "选项文本", "box": [x1, y1, x2, y2]},
    ...
  ],
  "buttons": {
    "previous": {"visible": bool, "text": "按钮文本", "box": [x1,y1,x2,y2]|null},
    "next": {"visible": bool, "text": "按钮文本", "box": [x1,y1,x2,y2]|null},
    "submit": {"visible": bool, "text": "按钮文本", "box": [x1,y1,x2,y2]|null}
  },
  "popup": {"visible": bool, "text": "弹窗文字", "buttons": []},
  "confidence": {"text": 0.0-1.0, "layout": 0.0-1.0}
}

规则:
- 不要输出 Markdown
- 不要输出解释文字
- 不要替用户做题
- 不要猜测无法看清的内容
- 如果无法识别，page_state 返回 "unknown"
- box 坐标基于本张截图的像素尺寸，不要使用屏幕坐标
```

## 附录 B: 文本模型提示词 (中文)

```
你只负责根据题干和选项判断答案。
请返回严格 JSON，不要输出其他内容。

输入格式: {"question_type": "...", "question": "...", "options": {"A": "...", "B": "...", ...}}
输出格式: {"question_type": "...", "answer": ["B"], "confidence": 0.88, "reason": "简短理由"}

规则:
- answer 字段必须是数组
- 单选题只返回一个选项，如 ["B"]
- 多选题可以返回多个选项，如 ["A", "C"]
- 无法确定时降低 confidence (< 0.5)
- 不要输出 Markdown
- 不要输出额外解释
- 不要返回页面坐标
- 不要返回点击动作
```

---

> **设计文档结束**。本文件是 ChaoxingAgent v1 的权威设计参考。实施时以此为准，如有偏离需更新本文档。
