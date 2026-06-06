# ChaoxingAgent v1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Windows 本地自动化答题工具 — 投屏窗口绑定 → 手动框选手机画面 → 视觉模型解析题目 → 文本模型作答 → 程序点击选项/下一题 → 循环至交卷停止。

**Architecture:** 四层结构（表示层/核心逻辑层/模型服务层/数据层），上层调用下层，坐标映射在核心层完成，模型层通过 `model_config` 间接工厂获取客户端，状态机串联 12 步单题循环。

**Tech Stack:** Python 3.10+ / uv / pywin32 / tkinter / pydantic v2 / OpenCV + numpy / requests

**Design doc:** `docs/superpowers/specs/2026-06-06-chaoxing-agent-design.md`

---

## File Structure

```
ChaoxingAgent/
├── main.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── config/
│   ├── config.json                  # 运行时配置模板
│   └── model_services.json          # 模型服务商模板
├── core/
│   ├── __init__.py
│   ├── errors.py                    # ChaoxingError / RecoverableError / PauseRequiredError / FatalStopError
│   ├── window_selector.py
│   ├── viewport_selector.py
│   ├── screen_capture.py
│   ├── coordinate_mapper.py
│   ├── click_executor.py
│   ├── page_change_detector.py
│   ├── state_machine.py
│   └── trace_logger.py
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
├── trace/                           # 运行时创建
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-06-06-chaoxing-agent-design.md
        └── plans/
            └── 2026-06-06-chaoxing-agent-plan.md  ← 本文件
```

---

### Task 0: 项目基础 — 配置模板、prompt文件、__init__、异常基类、pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt` (已存在，验证内容)
- Create: `config/config.json`
- Create: `config/model_services.json`
- Create: `prompts/vision_prompt.txt`
- Create: `prompts/solver_prompt.txt`
- Create: `core/__init__.py`
- Create: `models/__init__.py`
- Create: `schemas/__init__.py`
- Create: `core/errors.py`

- [ ] **Step 1: 创建 pyproject.toml**

```bash
cd D:/mytmp/ChaoxingAgent
```

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
```

- [ ] **Step 2: 验证 requirements.txt**

确认 `requirements.txt` 内容与 `pyproject.toml` 一致：

```
pywin32>=306
psutil>=5.9.0
Pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0
requests>=2.31.0
pydantic>=2.0.0
```

- [ ] **Step 3: 创建 config/config.json（默认模板）**

```json
{
  "target": {
    "process_name": "",
    "pid": null,
    "selected_hwnd": null,
    "window_title": "",
    "client_rect": [0, 0, 0, 0]
  },
  "viewport": {
    "lock_window_size_after_calibration": true,
    "phone_viewport_in_client": {
      "x": 0,
      "y": 0,
      "width": 0,
      "height": 0
    },
    "phone_viewport_ratio": {
      "x": 0.0,
      "y": 0.0,
      "width": 0.0,
      "height": 0.0
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

- [ ] **Step 4: 创建 config/model_services.json**

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

- [ ] **Step 5: 创建 prompts/vision_prompt.txt**

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

- [ ] **Step 6: 创建 prompts/solver_prompt.txt**

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

- [ ] **Step 7: 创建 core/errors.py**

```python
"""ChaoxingAgent 异常基类 — 三级异常模型"""


class ChaoxingError(Exception):
    """所有自定义异常的基类"""
    pass


class RecoverableError(ChaoxingError):
    """可恢复异常 — 自动重试，重试上限后升级为 PauseRequiredError"""
    pass


class PauseRequiredError(ChaoxingError):
    """需暂停异常 — 保存现场，通知用户，等待用户指令"""
    pass


class FatalStopError(ChaoxingError):
    """致命停止异常 — 保存 trace，退出"""
    pass
```

- [ ] **Step 8: 创建空的 __init__.py**

```bash
echo "" > D:/mytmp/ChaoxingAgent/core/__init__.py
echo "" > D:/mytmp/ChaoxingAgent/models/__init__.py
echo "" > D:/mytmp/ChaoxingAgent/schemas/__init__.py
```

- [ ] **Step 9: 初始化 uv 虚拟环境并安装依赖**

```bash
cd D:/mytmp/ChaoxingAgent
uv venv
uv pip install -r requirements.txt
```

- [ ] **Step 10: 验证**

```bash
uv run python -c "import psutil; import win32gui; import PIL; import cv2; import numpy; import pydantic; print('All deps OK')"
```

预期: `All deps OK`

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: bootstrap project — config templates, prompts, errors, pyproject.toml, uv venv"
```

---

### Task 1: 窗口选择 — `core/window_selector.py`

依赖: Task 0

**Files:**
- Create: `core/window_selector.py`

- [ ] **Step 1: 实现 WindowInfo 数据类**

```python
"""窗口选择器 — 根据 PID/进程名 找到并绑定 Windows 窗口"""

import psutil
import win32gui
import win32process
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    process_name: str
    window_title: str
    client_rect: tuple   # (left, top, right, bottom) — 客户区屏幕绝对坐标
    screen_rect: tuple   # (left, top, right, bottom) — 窗口整体屏幕坐标
    width: int           # client_rect 宽度
    height: int          # client_rect 高度


def _get_window_info(hwnd: int, pid: int, process_name: str) -> Optional[WindowInfo]:
    """从 hwnd 获取窗口详细信息"""
    title = win32gui.GetWindowText(hwnd)
    if not title:
        return None

    # 检查窗口尺寸
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width < 100 or height < 100:
        return None

    # 获取客户区
    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    # ClientToScreen 转换
    pt = win32gui.ClientToScreen(hwnd, (cl, ct))
    client_rect = (pt[0], pt[1], pt[0] + (cr - cl), pt[1] + (cb - ct))

    return WindowInfo(
        hwnd=hwnd,
        pid=pid,
        process_name=process_name,
        window_title=title,
        client_rect=client_rect,
        screen_rect=(left, top, right, bottom),
        width=cr - cl,
        height=cb - ct,
    )
```

- [ ] **Step 2: 实现进程查找函数**

```python
def find_processes_by_name(name: str) -> list[psutil.Process]:
    """根据进程名查找所有匹配进程"""
    name_lower = name.lower().removesuffix('.exe')
    matches = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info['name']
            if proc_name and name_lower in proc_name.lower().removesuffix('.exe'):
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matches


def find_process_by_pid(pid: int) -> Optional[psutil.Process]:
    """根据 PID 查找进程"""
    try:
        proc = psutil.Process(pid)
        return proc
    except psutil.NoSuchProcess:
        return None
```

- [ ] **Step 3: 实现窗口枚举函数**

```python
def _enum_visible_callback(hwnd: int, windows: list):
    """EnumWindows 回调"""
    if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
        windows.append(hwnd)
    return True


def enumerate_visible_windows(pid: int) -> list[WindowInfo]:
    """枚举指定 PID 的所有可见窗口"""
    all_visible = []
    win32gui.EnumWindows(_enum_visible_callback, all_visible)

    results = []
    for hwnd in all_visible:
        try:
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                proc = psutil.Process(pid)
                name = proc.name()
                info = _get_window_info(hwnd, pid, name)
                if info:
                    results.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results
```

- [ ] **Step 4: 实现交互选择函数**

```python
def _is_numeric(s: str) -> bool:
    return s.strip().isdigit()


def select_process(user_input: str) -> psutil.Process:
    """根据用户输入选择进程"""
    user_input = user_input.strip()

    if _is_numeric(user_input):
        pid = int(user_input)
        proc = find_process_by_pid(pid)
        if proc is None:
            raise SystemExit(f"未找到 PID={pid} 的进程")
        print(f"找到进程: PID={proc.pid} name={proc.name()}")
        return proc

    # 按进程名查找
    procs = find_processes_by_name(user_input)
    if not procs:
        raise SystemExit(f"未找到匹配 '{user_input}' 的进程")

    if len(procs) == 1:
        proc = procs[0]
        print(f"找到进程: PID={proc.pid} name={proc.name()}")
        return proc

    print(f"\n找到 {len(procs)} 个匹配进程:")
    for i, proc in enumerate(procs, 1):
        try:
            exe = proc.exe()
        except psutil.AccessDenied:
            exe = "(无法访问)"
        print(f"  [{i}] PID={proc.pid} name={proc.name()} exe={exe}")

    while True:
        choice = input(f"\n请选择进程编号 (1-{len(procs)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(procs):
                return procs[idx]
        except ValueError:
            pass
        print("无效选择，请重试")


def select_window(proc: psutil.Process) -> WindowInfo:
    """枚举进程下的可见窗口，让用户选择"""
    windows = enumerate_visible_windows(proc.pid)

    if not windows:
        raise SystemExit(f"PID={proc.pid} 下没有可见窗口。请确认窗口已打开且未最小化。")

    if len(windows) == 1:
        w = windows[0]
        print(f"\n绑定窗口: hwnd={w.hwnd} title='{w.window_title}' "
              f"rect={w.client_rect} size={w.width}x{w.height}")
        return w

    print(f"\nPID={proc.pid} 下有 {len(windows)} 个可见窗口:")
    for i, w in enumerate(windows, 1):
        print(f"  [{i}] hwnd={w.hwnd} title='{w.window_title}' "
              f"rect={w.client_rect} size={w.width}x{w.height}")

    while True:
        choice = input(f"\n请选择窗口编号 (1-{len(windows)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(windows):
                return windows[idx]
        except ValueError:
            pass
        print("无效选择，请重试")


def select(user_input: str) -> WindowInfo:
    """完整的选择流程: 用户输入 → 进程 → 窗口 → WindowInfo"""
    proc = select_process(user_input)
    return select_window(proc)
```

- [ ] **Step 5: 手动验证**

```bash
cd D:/mytmp/ChaoxingAgent
uv run python -c "
from core.window_selector import select
# 打开记事本后运行
w = select('notepad.exe')
print(f'OK: hwnd={w.hwnd} title={w.window_title} rect={w.client_rect} size={w.width}x{w.height}')
"
```

预期: 能列出记事本窗口并打印 hwnd/title/rect/size。

- [ ] **Step 6: Commit**

```bash
git add core/window_selector.py
git commit -m "feat: window_selector — PID/进程名查找，可见窗口枚举，交互选择"
```

---

### Task 2: 屏幕截图 — `core/screen_capture.py`

依赖: Task 0, Task 1

**Files:**
- Create: `core/screen_capture.py`

- [ ] **Step 1: 实现截图函数**

```python
"""窗口截图 — 截取客户区 / 裁剪手机画面"""

import win32gui
import win32ui
import win32con
from PIL import Image
from typing import Optional


def capture_client_area(hwnd: int) -> Image.Image:
    """截取窗口客户区，返回 PIL Image (RGB)"""
    # 获取客户区尺寸
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise RuntimeError(f"窗口客户区尺寸无效: {width}x{height}")

    # 获取窗口 DC
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    # 创建兼容位图
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)

    # BitBlt 截取客户区
    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

    # 转为 PIL Image
    bmp_info = bitmap.GetInfo()
    bmp_bits = bitmap.GetBitmapBits(True)
    img = Image.frombuffer('RGB', (bmp_info['bmWidth'], bmp_info['bmHeight']),
                           bmp_bits, 'raw', 'BGRX', 0, 1)

    # 清理
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return img


def capture_phone_screen(hwnd: int, viewport: dict) -> Image.Image:
    """截取手机画面区域 (根据 viewport 裁剪)"""
    full = capture_client_area(hwnd)

    vp = viewport["phone_viewport_in_client"]
    x, y, w, h = vp["x"], vp["y"], vp["width"], vp["height"]

    return full.crop((x, y, x + w, y + h))
```

- [ ] **Step 2: 实现窗口存活/尺寸检查**

```python
def check_window_alive(hwnd: int) -> bool:
    """检查窗口是否仍然存在"""
    try:
        return win32gui.IsWindow(hwnd) != 0
    except Exception:
        return False


def check_window_size_unchanged(hwnd: int, expected_client_rect: tuple,
                                max_ratio: float = 0.05) -> bool:
    """检查窗口客户区尺寸是否未明显变化"""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    cur_w = right - left
    cur_h = bottom - top

    exp_left, exp_top, exp_right, exp_bottom = expected_client_rect
    exp_w = exp_right - exp_left
    exp_h = exp_bottom - exp_top

    if exp_w <= 0 or exp_h <= 0:
        return True

    w_diff = abs(cur_w - exp_w) / exp_w
    h_diff = abs(cur_h - exp_h) / exp_h

    return w_diff <= max_ratio and h_diff <= max_ratio
```

- [ ] **Step 3: 手动验证**

```bash
uv run python -c "
from core.window_selector import select
from core.screen_capture import capture_client_area, check_window_alive, check_window_size_unchanged

w = select('notepad.exe')
img = capture_client_area(w.hwnd)
print(f'截图尺寸: {img.size}')
img.save('test_client_capture.png')
print('OK - 截图已保存到 test_client_capture.png')

alive = check_window_alive(w.hwnd)
print(f'窗口存活: {alive}')

unchanged = check_window_size_unchanged(w.hwnd, w.client_rect)
print(f'尺寸未变: {unchanged}')
"
```

预期: 截图尺寸与窗口大小一致。

- [ ] **Step 4: Commit**

```bash
git add core/screen_capture.py
git commit -m "feat: screen_capture — BitBlt 客户区截图，窗口存活/尺寸检查"
```

---

### Task 3: 手机画面区域选择 — `core/viewport_selector.py`

依赖: Task 2

**Files:**
- Create: `core/viewport_selector.py`

- [ ] **Step 1: 实现 ViewportInfo 数据类与 tkinter 框选 GUI**

```python
"""手机画面区域选择 — tkinter ROI 框选"""

import tkinter as tk
from PIL import Image, ImageTk
from dataclasses import dataclass
from typing import Optional

from core.screen_capture import capture_client_area
from core.window_selector import WindowInfo


@dataclass
class ViewportInfo:
    x: int
    y: int
    width: int
    height: int
    ratio_x: float
    ratio_y: float
    ratio_w: float
    ratio_h: float


class _ROISelector:
    """tkinter 内部类 — 显示截图，让用户拖拽框选"""

    def __init__(self, image: Image.Image, client_width: int, client_height: int):
        self.image = image
        self.client_width = client_width
        self.client_height = client_height
        self.result: Optional[ViewportInfo] = None

        self.root = tk.Tk()
        self.root.title("请框选手机画面区域（拖拽鼠标，按 Enter 确认，Esc 取消）")

        self.canvas = tk.Canvas(self.root, width=image.width, height=image.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        self.start_x = 0
        self.start_y = 0
        self.rect_id = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Return>", self._on_confirm)
        self.root.bind("<Escape>", self._on_cancel)

        # 按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="确认 (Enter)", command=self._on_confirm).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="重新选择", command=self._on_reset).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消 (Esc)", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.root.mainloop()

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='red', width=2
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        pass  # 矩形已创建

    def _on_confirm(self, event=None):
        if self.rect_id is None:
            return
        coords = self.canvas.coords(self.rect_id)
        if len(coords) != 4:
            return
        x1, y1, x2, y2 = [int(c) for c in coords]
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)

        if w < 20 or h < 20:
            return  # 选区太小

        self.result = ViewportInfo(
            x=x, y=y, width=w, height=h,
            ratio_x=x / self.client_width,
            ratio_y=y / self.client_height,
            ratio_w=w / self.client_width,
            ratio_h=h / self.client_height,
        )
        self.root.destroy()

    def _on_reset(self):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def _on_cancel(self, event=None):
        self.result = None
        self.root.destroy()


def select(window_info: WindowInfo) -> ViewportInfo:
    """截取窗口客户区 → tkinter 框选 → 返回 ViewportInfo"""
    print("\n正在截取窗口客户区...")
    img = capture_client_area(window_info.hwnd)
    print(f"客户区截图: {img.size}")

    selector = _ROISelector(img, window_info.width, window_info.height)

    if selector.result is None:
        raise SystemExit("用户取消了手机画面区域选择。")

    vp = selector.result
    print(f"\n手机画面区域 (相对客户区像素):")
    print(f"  x={vp.x} y={vp.y} width={vp.width} height={vp.height}")
    print(f"比例坐标:")
    print(f"  ratio_x={vp.ratio_x:.4f} ratio_y={vp.ratio_y:.4f} "
          f"ratio_w={vp.ratio_w:.4f} ratio_h={vp.ratio_h:.4f}")

    return vp
```

- [ ] **Step 2: 手动验证**（需要实际运行 tkinter GUI）

```bash
uv run python -c "
from core.window_selector import select as sel_win
from core.viewport_selector import select as sel_vp

w = sel_win('notepad.exe')
vp = sel_vp(w)
print(f'Viewport: x={vp.x} y={vp.y} w={vp.width} h={vp.height}')
print(f'Ratio: rx={vp.ratio_x:.4f} ry={vp.ratio_y:.4f} rw={vp.ratio_w:.4f} rh={vp.ratio_h:.4f}')
"
```

预期: 弹出 tkinter 窗口，可以拖拽选择区域，确认后打印坐标。

- [ ] **Step 3: Commit**

```bash
git add core/viewport_selector.py
git commit -m "feat: viewport_selector — tkinter ROI 框选，像素+比例坐标"
```

---

### Task 4: 坐标映射 — `core/coordinate_mapper.py`

依赖: Task 1, Task 3

**Files:**
- Create: `core/coordinate_mapper.py`

- [ ] **Step 1: 实现 CoordinateMapper**

```python
"""坐标映射 — 手机截图像素坐标 ↔ Windows 屏幕坐标"""

import win32gui
from typing import Optional


class CoordinateMapper:
    """将手机截图内的像素坐标转换为 Windows 屏幕绝对坐标"""

    def __init__(self, hwnd: int, viewport: dict):
        self.hwnd = hwnd

        # 获取当前客户区屏幕位置
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (cl, ct))
        self.client_screen_left = pt[0]
        self.client_screen_top = pt[1]

        # viewport 偏移
        vp = viewport["phone_viewport_in_client"]
        self.vp_x = vp["x"]
        self.vp_y = vp["y"]

        # 手机画面左上角在屏幕上的位置
        self._phone_left = self.client_screen_left + self.vp_x
        self._phone_top = self.client_screen_top + self.vp_y

    def refresh(self):
        """重新计算屏幕位置（窗口可能移动了）"""
        cl, ct, cr, cb = win32gui.GetClientRect(self.hwnd)
        pt = win32gui.ClientToScreen(self.hwnd, (cl, ct))
        self.client_screen_left = pt[0]
        self.client_screen_top = pt[1]
        self._phone_left = self.client_screen_left + self.vp_x
        self._phone_top = self.client_screen_top + self.vp_y

    def image_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """手机截图内像素坐标 → 屏幕绝对坐标"""
        return (self._phone_left + x, self._phone_top + y)

    def box_center_screen(self, box: list[int]) -> tuple[int, int]:
        """box [x1, y1, x2, y2] → 屏幕中心点坐标"""
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        return self.image_to_screen(cx, cy)
```

- [ ] **Step 2: 手动验证**

```bash
uv run python -c "
from core.window_selector import select
from core.coordinate_mapper import CoordinateMapper

w = select('notepad.exe')
# 手动构造一个 viewport
viewport = {'phone_viewport_in_client': {'x': 0, 'y': 0, 'width': w.width, 'height': w.height}}
mapper = CoordinateMapper(w.hwnd, viewport)

# 测试: 图片中心 → 屏幕坐标
cx, cy = w.width // 2, w.height // 2
sx, sy = mapper.image_to_screen(cx, cy)
print(f'图片中心点 ({cx}, {cy}) → 屏幕坐标 ({sx}, {sy})')
print(f'客户区左上角屏幕坐标: ({mapper.client_screen_left}, {mapper.client_screen_top})')
"
```

预期: 图片中心点映射到客户区中心，坐标=client_screen + 半宽/半高。

- [ ] **Step 3: Commit**

```bash
git add core/coordinate_mapper.py
git commit -m "feat: coordinate_mapper — 手机截图像素坐标 → Windows 屏幕坐标"
```

---

### Task 5: 数据校验 Schema — `schemas/`

依赖: Task 0

**Files:**
- Create: `schemas/vision_schema.py`
- Create: `schemas/solver_schema.py`

- [ ] **Step 1: 实现 vision_schema.py**

```python
"""视觉模型输出 Pydantic 校验模型"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class VisionOption(BaseModel):
    key: str
    text: str
    box: list[int]  # [x1, y1, x2, y2] — 手机截图内像素坐标


class VisionButton(BaseModel):
    visible: bool
    text: str = ""
    box: Optional[list[int]] = None


class VisionButtons(BaseModel):
    previous: VisionButton
    next: VisionButton
    submit: VisionButton


class VisionPopup(BaseModel):
    visible: bool = False
    text: str = ""
    buttons: list = Field(default_factory=list)


class VisionConfidence(BaseModel):
    text: float   # 文字识别置信度 0~1
    layout: float  # 布局识别置信度 0~1


class VisionResult(BaseModel):
    page_state: Literal["question", "submit", "popup", "loading", "finished", "unknown"]
    question_type: Literal["single_choice", "multiple_choice", "true_false", "fill_blank", "unknown"]
    question_text: str = ""
    options: list[VisionOption] = Field(default_factory=list)
    buttons: VisionButtons
    popup: VisionPopup = Field(default_factory=VisionPopup)
    confidence: VisionConfidence
```

- [ ] **Step 2: 实现 solver_schema.py**

```python
"""文本模型输出 Pydantic 校验模型"""

from pydantic import BaseModel, Field


class SolverResult(BaseModel):
    question_type: str
    answer: list[str]   # 必须是数组，单选如 ["B"]，多选如 ["A", "C"]
    confidence: float
    reason: str = ""
```

- [ ] **Step 3: 验证 Pydantic 模型可正常构造**

```bash
uv run python -c "
from schemas.vision_schema import VisionResult, VisionButtons, VisionButton, VisionOption, VisionConfidence

# 构造最小合法 VisionResult
vr = VisionResult(
    page_state='question',
    question_type='single_choice',
    question_text='1+1=?',
    options=[
        VisionOption(key='A', text='2', box=[80,520,960,620]),
        VisionOption(key='B', text='3', box=[80,650,960,750]),
    ],
    buttons=VisionButtons(
        previous=VisionButton(visible=True, text='上一题', box=[80,1720,360,1810]),
        next=VisionButton(visible=True, text='下一题', box=[700,1720,1000,1810]),
        submit=VisionButton(visible=False),
    ),
    confidence=VisionConfidence(text=0.9, layout=0.92),
)
print(f'VisionResult OK: page_state={vr.page_state}, options={len(vr.options)}')

from schemas.solver_schema import SolverResult
sr = SolverResult(question_type='single_choice', answer=['A'], confidence=0.88, reason='1+1=2')
print(f'SolverResult OK: answer={sr.answer}')
"
```

预期: `VisionResult OK` + `SolverResult OK`

- [ ] **Step 4: Commit**

```bash
git add schemas/vision_schema.py schemas/solver_schema.py
git commit -m "feat: schemas — VisionResult / SolverResult Pydantic v2 校验模型"
```

---

### Task 6: 模型配置与客户端 — `models/`

依赖: Task 0

**Files:**
- Create: `models/model_config.py`
- Create: `models/base_client.py`
- Create: `models/openai_client.py`
- Create: `models/google_client.py`

- [ ] **Step 1: 实现 model_config.py**

```python
"""模型配置 — 读取 model_services.json + 客户端工厂"""

import json
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ModelConfig:
    api_type: str      # "openai" | "google"
    base_url: str
    api_key: str       # 已从环境变量读取的实际值
    model_id: str


def _get_config_dir() -> Path:
    return Path(__file__).parent.parent / "config"


def load_model_services() -> dict:
    """读取 model_services.json"""
    path = _get_config_dir() / "model_services.json"
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_api_key(env_var: str) -> str:
    """从环境变量读取 API Key"""
    key = os.environ.get(env_var, '')
    if not key:
        raise RuntimeError(
            f"环境变量 {env_var} 未设置。请设置后重试。\n"
            f"示例: set {env_var}=your-api-key"
        )
    return key


def get_vision_config(services: dict) -> ModelConfig:
    """根据 selected.vision_model 获取视觉模型配置"""
    selected_key = services["selected"]["vision_model"]
    entry = services["model_services"]["vision"][selected_key]
    return ModelConfig(
        api_type=entry["api_type"],
        base_url=entry["base_url"],
        api_key=_get_api_key(entry["api_key_env"]),
        model_id=entry["model_id"],
    )


def get_solver_config(services: dict) -> ModelConfig:
    """根据 selected.solver_model 获取文本模型配置"""
    selected_key = services["selected"]["solver_model"]
    entry = services["model_services"]["solver"][selected_key]
    return ModelConfig(
        api_type=entry["api_type"],
        base_url=entry["base_url"],
        api_key=_get_api_key(entry["api_key_env"]),
        model_id=entry["model_id"],
    )
```

- [ ] **Step 2: 实现 base_client.py**

```python
"""模型客户端抽象基类"""

from abc import ABC, abstractmethod


class BaseModelClient(ABC):
    """所有模型客户端的抽象基类"""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """发送请求，返回模型原始响应文本"""
        ...
```

- [ ] **Step 3: 实现 openai_client.py**

```python
"""OpenAI 兼容 API 客户端"""

import requests
from models.base_client import BaseModelClient
from models.model_config import ModelConfig


class OpenAIClient(BaseModelClient):
    def __init__(self, config: ModelConfig):
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.model_id = config.model_id

    def chat(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: 实现 google_client.py**

```python
"""Google Gemini API 客户端"""

import requests
from models.base_client import BaseModelClient
from models.model_config import ModelConfig


class GoogleClient(BaseModelClient):
    def __init__(self, config: ModelConfig):
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.model_id = config.model_id

    def chat(self, messages: list[dict]) -> str:
        url = (f"{self.base_url}/v1beta/models/{self.model_id}:generateContent"
               f"?key={self.api_key}")

        # 转换 OpenAI 格式 messages → Gemini contents 格式
        contents = []
        for msg in messages:
            parts = []
            if isinstance(msg.get("content"), str):
                parts.append({"text": msg["content"]})
            elif isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "text":
                        parts.append({"text": item["text"]})
                    elif item.get("type") == "image_url":
                        data_url = item["image_url"]["url"]
                        # data:image/png;base64,xxx → extract mime + base64 data
                        header, b64 = data_url.split(",", 1)
                        mime = header.replace("data:", "").replace(";base64", "")
                        parts.append({
                            "inline_data": {
                                "mime_type": mime,
                                "data": b64,
                            }
                        })
            if not parts:
                continue
            role = "user" if msg.get("role") == "user" else "model"
            # system prompt 处理: 合并到第一条 user message 前面
            contents.append({"role": role, "parts": parts})

        # 处理 system message: 作为第一条 user message 的 prefix
        system_text = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
                break
        if system_text and contents:
            contents[0]["parts"].insert(0, {"text": f"[System Instruction]\n{system_text}\n\nPlease follow the system instruction above."})

        body = {
            "contents": contents,
            "generationConfig": {
                "response_mime_type": "application/json",
            },
        }

        resp = requests.post(url, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        # 提取文本
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        return parts[0]["text"] if parts else ""
```

- [ ] **Step 5: 验证 model_config 可加载**

```bash
uv run python -c "
from models.model_config import load_model_services

services = load_model_services()
print(f'Vision providers: {list(services[\"model_services\"][\"vision\"].keys())}')
print(f'Solver providers: {list(services[\"model_services\"][\"solver\"].keys())}')
print(f'Selected vision: {services[\"selected\"][\"vision_model\"]}')
print(f'Selected solver: {services[\"selected\"][\"solver_model\"]}')
print('model_config OK')
"
```

预期: 打印 4 行 provider 信息 + `model_config OK`。

- [ ] **Step 6: Commit**

```bash
git add models/model_config.py models/base_client.py models/openai_client.py models/google_client.py
git commit -m "feat: model clients — model_config, openai_client, google_client, base_client"
```

---

### Task 7: 视觉解析 — `models/vision_parser.py`

依赖: Task 5, Task 6

**Files:**
- Create: `models/vision_parser.py`

- [ ] **Step 1: 实现 vision_parser.py**

```python
"""视觉模型解析 — 截图 → VisionResult"""

import json
import re
import base64
import io
from PIL import Image
from pathlib import Path

from models.model_config import ModelConfig
from models.openai_client import OpenAIClient
from models.google_client import GoogleClient
from schemas.vision_schema import VisionResult
from core.errors import RecoverableError, PauseRequiredError


def _load_prompt() -> str:
    """读取视觉模型提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "vision_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"视觉模型提示词文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding='utf-8')


def _image_to_base64_url(image: Image.Image) -> str:
    """PIL Image → base64 data URL"""
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64}"


def _extract_json(text: str) -> dict:
    """从模型返回文本中提取 JSON"""
    # 先尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 正则提取 JSON 块
    # 尝试 ```json ... ```
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试第一个 { ... } 匹配
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    continue

    raise RecoverableError("无法从模型返回内容中提取 JSON")


def parse(image: Image.Image, config: ModelConfig) -> VisionResult:
    """发送手机截图到视觉模型，返回结构化 VisionResult"""
    prompt = _load_prompt()
    b64_url = _image_to_base64_url(image)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [
            {"type": "text", "text": f"图片尺寸: {image.width}x{image.height}，请解析页面结构。"},
            {"type": "image_url", "image_url": {"url": b64_url}},
        ]},
    ]

    # 根据 api_type 选择客户端
    if config.api_type == "openai":
        client = OpenAIClient(config)
    elif config.api_type == "google":
        client = GoogleClient(config)
    else:
        raise PauseRequiredError(f"不支持的 api_type: {config.api_type}")

    raw_text = client.chat(messages)
    raw_json = _extract_json(raw_text)

    try:
        result = VisionResult.model_validate(raw_json)
    except Exception as e:
        raise PauseRequiredError(f"视觉模型返回 JSON 校验失败: {e}\n原始内容: {raw_text[:500]}")

    return result
```

- [ ] **Step 2: Commit**

```bash
git add models/vision_parser.py
git commit -m "feat: vision_parser — 截图→base64→视觉模型→JSON提取→VisionResult"
```

---

### Task 8: 文本作答 — `models/text_solver.py`

依赖: Task 5, Task 6

**Files:**
- Create: `models/text_solver.py`

- [ ] **Step 1: 实现 text_solver.py**

```python
"""文本模型作答 — 题干+选项 → SolverResult"""

import json
import re
from pathlib import Path

from models.model_config import ModelConfig
from models.openai_client import OpenAIClient
from models.google_client import GoogleClient
from schemas.solver_schema import SolverResult
from core.errors import RecoverableError, PauseRequiredError


def _load_prompt() -> str:
    """读取文本模型提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "solver_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"文本模型提示词文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding='utf-8')


def _extract_json(text: str) -> dict:
    """从模型返回文本中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    continue

    raise RecoverableError("无法从模型返回内容中提取 JSON")


def solve(question_type: str, question_text: str, options: dict[str, str],
          config: ModelConfig) -> SolverResult:
    """发送题干+选项到文本模型，返回 SolverResult"""
    prompt = _load_prompt()

    input_obj = {
        "question_type": question_type,
        "question": question_text,
        "options": options,
    }

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(input_obj, ensure_ascii=False)},
    ]

    if config.api_type == "openai":
        client = OpenAIClient(config)
    elif config.api_type == "google":
        client = GoogleClient(config)
    else:
        raise PauseRequiredError(f"不支持的 api_type: {config.api_type}")

    raw_text = client.chat(messages)
    raw_json = _extract_json(raw_text)

    try:
        result = SolverResult.model_validate(raw_json)
    except Exception as e:
        raise PauseRequiredError(f"文本模型返回 JSON 校验失败: {e}\n原始内容: {raw_text[:500]}")

    return result
```

- [ ] **Step 2: Commit**

```bash
git add models/text_solver.py
git commit -m "feat: text_solver — 题干+选项→文本模型→JSON提取→SolverResult"
```

---

### Task 9: 点击执行 — `core/click_executor.py`

依赖: Task 4

**Files:**
- Create: `core/click_executor.py`

- [ ] **Step 1: 实现 click_executor.py**

```python
"""鼠标点击执行器 — 使用 ctypes + SendInput"""

import ctypes
import time
from ctypes import wintypes

from core.coordinate_mapper import CoordinateMapper

# Windows API 常量
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

# SendInput 结构体
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT),
    ]


def _to_screen_coords(x: int, y: int) -> tuple[int, int]:
    """像素坐标 → 屏幕归一化坐标 (0~65535)"""
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    nx = int(x * 65535 / screen_w)
    ny = int(y * 65535 / screen_h)
    return nx, ny


def click_at(x: int, y: int):
    """在屏幕坐标 (x, y) 执行鼠标左键点击（使用 SendInput）"""
    nx, ny = _to_screen_coords(x, y)

    # 移动到目标位置
    down = INPUT()
    down.type = INPUT_MOUSE
    down.mi.dx = nx
    down.mi.dy = ny
    down.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN

    up = INPUT()
    up.type = INPUT_MOUSE
    up.mi.dx = nx
    up.mi.dy = ny
    up.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP

    ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    time.sleep(0.02)
    ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def click_options(answers: list[str], options: list, mapper: CoordinateMapper, timing: dict):
    """
    根据答案 key 依次点击对应选项。

    answers: ["A", "C"]
    options: VisionOption 对象列表 (有 key, box 属性)
    mapper: CoordinateMapper 实例
    timing: config["timing"] 字典
    """
    option_map = {opt.key: opt for opt in options}

    for i, answer_key in enumerate(answers):
        opt = option_map[answer_key]
        sx, sy = mapper.box_center_screen(opt.box)
        print(f"  [点击选项 {answer_key}] 截图坐标: {opt.box} → 屏幕坐标: ({sx}, {sy})")
        click_at(sx, sy)

        # 多选时选项之间等待
        if len(answers) > 1 and i < len(answers) - 1:
            time.sleep(timing.get("between_multi_select_clicks", 0.2))


def click_next_button(box: list[int], mapper: CoordinateMapper, timing: dict):
    """点击下一题按钮（含前后等待）"""
    # 点击前等待
    before_wait = timing.get("before_click_next", 0.2)
    time.sleep(before_wait)

    sx, sy = mapper.box_center_screen(box)
    print(f"  [点击下一题] 截图坐标: {box} → 屏幕坐标: ({sx}, {sy})")
    click_at(sx, sy)

    # 点击后等待
    after_wait = timing.get("after_click_next", 0.5)
    time.sleep(after_wait)
```

- [ ] **Step 2: 手动验证**（用记事本做点击测试）

```bash
uv run python -c "
from core.window_selector import select
from core.coordinate_mapper import CoordinateMapper
from core.click_executor import click_at

# 打开记事本后运行，点击菜单栏区域
w = select('notepad.exe')
viewport = {'phone_viewport_in_client': {'x': 0, 'y': 0, 'width': w.width, 'height': w.height}}
mapper = CoordinateMapper(w.hwnd, viewport)

# 点击客户区中心点下方一点 (大概菜单位置)
cx, cy = w.width // 2, 30
sx, sy = mapper.image_to_screen(cx, cy)
print(f'即将点击屏幕 ({sx}, {sy})')
import time; time.sleep(2)
click_at(sx, sy)
print('已点击')
"
```

预期: 鼠标移动到记事本中心偏上区域并点击，记事本"文件"菜单弹开。

- [ ] **Step 3: Commit**

```bash
git add core/click_executor.py
git commit -m "feat: click_executor — SendInput 鼠标点击，选项/下一题点击，多选间隔"
```

---

### Task 10: 页面变化检测 — `core/page_change_detector.py`

依赖: Task 2

**Files:**
- Create: `core/page_change_detector.py`

- [ ] **Step 1: 实现 page_change_detector.py**

```python
"""页面变化检测 — 灰度差异判断题目是否跳转"""

import time
import numpy as np
from PIL import Image
from typing import Callable, Optional


def _crop_question_region(img: Image.Image, region: dict) -> np.ndarray:
    """裁剪题目区域 → 灰度 → 缩放"""
    w, h = img.size
    x1 = int(w * region["x1"])
    y1 = int(h * region["y1"])
    x2 = int(w * region["x2"])
    y2 = int(h * region["y2"])

    cropped = img.crop((x1, y1, x2, y2))
    gray = cropped.convert('L')
    resized = gray.resize((200, 200), Image.LANCZOS)
    return np.array(resized, dtype=np.float32)


def detect(before: Image.Image, after: Image.Image,
           region: dict, threshold: float, _resize: tuple = (200, 200)) -> bool:
    """比较两张截图的题目区域差异（忽略 _resize，固定 200x200）"""
    before_arr = _crop_question_region(before, region)
    after_arr = _crop_question_region(after, region)

    diff = np.abs(before_arr - after_arr) / 255.0
    changed_ratio = float(np.mean(diff > 0.1))

    return changed_ratio > threshold, changed_ratio


def wait_for_change(before: Image.Image,
                    capture_fn: Callable[[], Image.Image],
                    config: dict) -> tuple[bool, Optional[Image.Image]]:
    """
    等待页面变化，最多等到 max_page_change_wait 秒。

    返回: (是否变化, 最新截图)
    """
    page_change_cfg = config.get("page_change", {})
    timing = config.get("timing", {})
    thresholds = config.get("thresholds", {})

    region = page_change_cfg.get("compare_region_ratio", {
        "x1": 0.0, "y1": 0.08, "x2": 1.0, "y2": 0.75
    })
    threshold = thresholds.get("page_change_pixel_ratio", 0.03)
    extra_wait = timing.get("extra_wait_if_page_not_changed", 0.5)
    max_wait = timing.get("max_page_change_wait", 3.0)

    # 第一次检测（已经等待了 after_click_next）
    after = capture_fn()
    changed, ratio = detect(before, after, region, threshold)
    print(f"  页面变化检测: ratio={ratio:.4f} threshold={threshold} changed={changed}")

    if changed:
        return True, after

    # 未变化，额外等待重试
    elapsed = timing.get("after_click_next", 0.5)
    while elapsed < max_wait:
        time.sleep(extra_wait)
        elapsed += extra_wait
        after = capture_fn()
        changed, ratio = detect(before, after, region, threshold)
        print(f"  重试检测 ({elapsed:.1f}s): ratio={ratio:.4f} changed={changed}")
        if changed:
            return True, after

    return False, after
```

- [ ] **Step 2: 手动验证**（用两张不同截图测试）

```bash
uv run python -c "
from PIL import Image
import numpy as np
from core.page_change_detector import detect

# 生成两张不同的测试图
img1 = Image.fromarray(np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8))
img2 = Image.fromarray(np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8))
# 相同图
img3 = img1.copy()

region = {'x1': 0.0, 'y1': 0.0, 'x2': 1.0, 'y2': 1.0}

changed, ratio = detect(img1, img2, region, 0.03)
print(f'不同图片: changed={changed} ratio={ratio:.4f}')

changed, ratio = detect(img1, img3, region, 0.03)
print(f'相同图片: changed={changed} ratio={ratio:.4f}')
"
```

预期: 不同图片 ratio > 0.03 → changed=True；相同图片 ratio ≈ 0 → changed=False。

- [ ] **Step 3: Commit**

```bash
git add core/page_change_detector.py
git commit -m "feat: page_change_detector — 裁剪→灰度→缩放→像素差异比例检测"
```

---

### Task 11: Trace 日志 — `core/trace_logger.py`

依赖: Task 0

**Files:**
- Create: `core/trace_logger.py`

- [ ] **Step 1: 实现 trace_logger.py**

```python
"""Trace 日志 — 每步截图 + JSON 落盘"""

import json
from pathlib import Path
from datetime import datetime


class TraceLogger:
    """管理 trace/ 目录，保存每步截图和 JSON"""

    def __init__(self, base_dir: str = "trace"):
        self.base_dir = Path(base_dir)

        # 按启动时间创建 session 子目录
        session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = self.base_dir / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)

        print(f"[Trace] 日志目录: {self.session_dir}")

    def save_step(self, step_data: dict):
        """保存一步的截图和 JSON"""
        step_num = step_data["step"]
        timestamp = datetime.now().isoformat()

        # 保存截图
        screenshot_filename = f"step_{step_num:03d}.png"
        screenshot_path = self.session_dir / screenshot_filename
        img = step_data.pop("screenshot_img", None)
        if img:
            img.save(screenshot_path)

        # 构建 JSON
        trace_entry = {
            "step": step_num,
            "timestamp": timestamp,
            "screenshot": str(screenshot_path),
            "page_state": step_data.get("page_state"),
            "question_type": step_data.get("question_type"),
            "question": step_data.get("question", ""),
            "options": step_data.get("options"),
            "vision_confidence": step_data.get("vision_confidence"),
            "vision_raw_json": step_data.get("vision_raw_json"),
            "solver_answer": step_data.get("solver_answer"),
            "solver_confidence": step_data.get("solver_confidence"),
            "solver_reason": step_data.get("solver_reason", ""),
            "solver_raw_json": step_data.get("solver_raw_json"),
            "clicked_options": step_data.get("clicked_options", []),
            "next_button": step_data.get("next_button"),
            "page_changed": step_data.get("page_changed"),
            "page_change_ratio": step_data.get("page_change_ratio"),
            "error": step_data.get("error"),
        }

        # 保存 JSON
        json_filename = f"step_{step_num:03d}.json"
        json_path = self.session_dir / json_filename
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(trace_entry, f, ensure_ascii=False, indent=2)

    def save_pause(self, step_num: int, screenshot, vision_result: dict,
                   solver_result: dict | None, reason: str):
        """暂停时额外保存现场"""
        pause_dir = self.session_dir / f"pause_step_{step_num:03d}"
        pause_dir.mkdir(exist_ok=True)

        if screenshot:
            screenshot.save(pause_dir / "screenshot_at_pause.png")

        with open(pause_dir / "vision_result.json", 'w', encoding='utf-8') as f:
            json.dump(vision_result, f, ensure_ascii=False, indent=2)

        if solver_result:
            with open(pause_dir / "solver_result.json", 'w', encoding='utf-8') as f:
                json.dump(solver_result, f, ensure_ascii=False, indent=2)

        (pause_dir / "pause_reason.txt").write_text(reason, encoding='utf-8')

    def save_stop(self, reason: str):
        """最终停止时记录原因"""
        (self.session_dir / "STOP_REASON.txt").write_text(reason, encoding='utf-8')
```

- [ ] **Step 2: 验证**

```bash
uv run python -c "
from core.trace_logger import TraceLogger
from PIL import Image

tl = TraceLogger('trace')
img = Image.new('RGB', (100, 100), 'red')
tl.save_step({
    'step': 1,
    'screenshot_img': img,
    'page_state': 'question',
    'question_type': 'single_choice',
    'question': 'test',
    'options': {'A': 'aaa'},
    'vision_confidence': {'text': 0.9, 'layout': 0.9},
    'solver_answer': ['A'],
    'solver_confidence': 0.88,
    'clicked_options': [],
    'page_changed': True,
    'error': None,
})
print('Trace 文件已生成')
import os
for f in os.listdir(tl.session_dir):
    print(f'  {f}')
"
```

预期: trace 目录下出现 session_xxx 子目录，包含 step_001.png 和 step_001.json。

- [ ] **Step 3: Commit**

```bash
git add core/trace_logger.py
git commit -m "feat: trace_logger — 按 session 保存每步截图+JSON，暂停现场保存"
```

---

### Task 12: 状态机 — `core/state_machine.py`

依赖: Task 1~11 全部

**Files:**
- Create: `core/state_machine.py`

- [ ] **Step 1: 实现 StateMachine**

```python
"""状态机 — 主循环编排，串联全部流程"""

import json
import time
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from core.errors import RecoverableError, PauseRequiredError, FatalStopError
from core.screen_capture import capture_phone_screen, check_window_alive, check_window_size_unchanged
from core.coordinate_mapper import CoordinateMapper
from core.click_executor import click_options, click_next_button
from core.page_change_detector import wait_for_change
from core.trace_logger import TraceLogger
from models.model_config import load_model_services, get_vision_config, get_solver_config
from models.vision_parser import parse as vision_parse
from models.text_solver import solve as text_solve


@dataclass
class StepResult:
    should_stop: bool = False
    stop_reason: str = ""
    step_data: dict = field(default_factory=dict)


class StateMachine:
    """主循环状态机"""

    def __init__(self, config: dict, model_services: dict):
        self.config = config
        self.model_services = model_services

        target = config["target"]
        hwnd = target["selected_hwnd"]
        if not hwnd:
            raise FatalStopError("未绑定目标窗口，请先运行窗口选择。")

        self.hwnd = hwnd
        self.expected_client_rect = tuple(target.get("client_rect", (0, 0, 0, 0)))

        viewport = config["viewport"]
        if not viewport["phone_viewport_in_client"]["width"]:
            raise FatalStopError("未标定手机画面区域，请先运行区域选择。")

        self.viewport = viewport
        self.mapper = CoordinateMapper(self.hwnd, viewport)

        self.vision_config = get_vision_config(model_services)
        self.solver_config = get_solver_config(model_services)

        self.trace_logger = TraceLogger()

        self.step = 0
        self.consecutive_errors = 0

        runtime = config.get("runtime", {})
        self.max_steps = runtime.get("max_steps", 200)
        self.max_consecutive_errors = runtime.get("max_consecutive_errors", 3)
        self.loading_retry_max = runtime.get("loading_retry_max", 3)
        self.loading_retry_delay = runtime.get("loading_retry_delay", 1.0)
        self.stop_on_submit = runtime.get("stop_on_submit", True)
        self.pause_on_popup = runtime.get("pause_on_popup", True)
        self.pause_on_unknown = runtime.get("pause_on_unknown", True)

        self.thresholds = config.get("thresholds", {})
        self.timing = config.get("timing", {})

    def run(self):
        """主循环入口"""
        print(f"\n{'='*50}")
        print(f"ChaoxingAgent v1 — 开始自动循环")
        print(f"最大步骤数: {self.max_steps}")
        print(f"{'='*50}\n")

        try:
            while self.step < self.max_steps:
                self.mapper.refresh()

                try:
                    result = self._process_one_step()
                except RecoverableError as e:
                    self.consecutive_errors += 1
                    print(f"[WARN] 可恢复异常 (第{self.consecutive_errors}次): {e}")
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        raise FatalStopError(f"连续异常超过 {self.max_consecutive_errors} 次")
                    time.sleep(1)
                    continue

                if result.should_stop:
                    self._handle_stop(result)
                    return

                self.step += 1
                self.consecutive_errors = 0

        except FatalStopError as e:
            print(f"\n[FATAL] {e}")
            self.trace_logger.save_stop(str(e))
        except KeyboardInterrupt:
            print("\n[INFO] 用户中断")
            self.trace_logger.save_stop("用户中断 (Ctrl+C)")

        print(f"\n处理完成。共处理 {self.step} 题。")
        print(f"Trace 目录: {self.trace_logger.session_dir}")

    def _process_one_step(self) -> StepResult:
        """处理一道题的完整流程"""
        print(f"\n--- Step {self.step + 1} ---")

        # 1. 检查窗口
        if not check_window_alive(self.hwnd):
            return StepResult(should_stop=True, stop_reason="window_gone")

        if not check_window_size_unchanged(self.hwnd, self.expected_client_rect,
                                           self.thresholds.get("window_size_change_ratio", 0.05)):
            self._pause("窗口尺寸已变化，请重新标定手机画面区域")

        # 2. 截图
        screenshot = capture_phone_screen(self.hwnd, self.viewport)
        print(f"  截图: {screenshot.width}x{screenshot.height}")

        # 3. 视觉解析
        vision = vision_parse(screenshot, self.vision_config)
        print(f"  page_state={vision.page_state} type={vision.question_type} "
              f"confidence(text={vision.confidence.text:.2f} layout={vision.confidence.layout:.2f})")

        # 4. GUARD: page_state 检查
        if vision.page_state == "submit" or vision.buttons.submit.visible:
            return StepResult(should_stop=True, stop_reason="submit_detected")

        if vision.popup.visible and self.pause_on_popup:
            self._pause_save(screenshot, vision, None, "检测到弹窗，请手动处理后按 Enter 继续")
            return StepResult()

        if vision.page_state == "unknown" and self.pause_on_unknown:
            self._pause_save(screenshot, vision, None, "无法识别页面状态，请检查后按 Enter 继续")
            return StepResult()

        if vision.page_state == "loading":
            return self._handle_loading(screenshot)

        if vision.page_state != "question":
            self._pause_save(screenshot, vision, None,
                           f"未预期的页面状态: {vision.page_state}，请检查后按 Enter 继续")
            return StepResult()

        # 视觉置信度检查
        vt = self.thresholds.get("vision_text_confidence", 0.75)
        vl = self.thresholds.get("vision_layout_confidence", 0.75)
        if vision.confidence.text < vt or vision.confidence.layout < vl:
            self._pause_save(screenshot, vision, None,
                           f"视觉置信度过低 (text={vision.confidence.text:.2f} layout={vision.confidence.layout:.2f})")

        # 检查选项
        if not vision.options:
            self._pause_save(screenshot, vision, None, "视觉模型未识别到选项")
            return StepResult()

        # 检查下一题按钮
        if not vision.buttons.next.visible or not vision.buttons.next.box:
            self._pause_save(screenshot, vision, None, "未识别到下一题按钮")
            return StepResult()

        # 5. 文本答题
        opts_dict = {opt.key: opt.text for opt in vision.options}
        print(f"  题干: {vision.question_text[:80]}...")
        print(f"  选项: {opts_dict}")

        solver = text_solve(vision.question_type, vision.question_text,
                           opts_dict, self.solver_config)
        print(f"  答案: {solver.answer} confidence={solver.confidence:.2f}")

        # 6. GUARD: 答案校验
        if solver.confidence < self.thresholds.get("solver_confidence", 0.70):
            self._pause_save(screenshot, vision, solver,
                           f"文本模型置信度过低 ({solver.confidence:.2f})")
            return StepResult()

        for answer in solver.answer:
            if answer not in opts_dict:
                self._pause_save(screenshot, vision, solver,
                               f"答案 '{answer}' 无法映射到选项 {list(opts_dict.keys())}")
                return StepResult()

        # 7. 点击选项
        click_options(solver.answer, vision.options, self.mapper, self.timing)

        # 记录点击详情
        clicked = []
        for answer_key in solver.answer:
            opt = next(o for o in vision.options if o.key == answer_key)
            scx, scy = self.mapper.box_center_screen(opt.box)
            clicked.append({
                "key": answer_key,
                "box": opt.box,
                "image_center": [(opt.box[0] + opt.box[2]) // 2, (opt.box[1] + opt.box[3]) // 2],
                "screen_center": [scx, scy],
            })

        # 8. 截图 before
        before_img = capture_phone_screen(self.hwnd, self.viewport)

        # 9. 点击下一题
        click_next_button(vision.buttons.next.box, self.mapper, self.timing)

        # 10. 页面变化检测
        def _capture():
            return capture_phone_screen(self.hwnd, self.viewport)

        changed, after_img = wait_for_change(before_img, _capture, self.config)

        if not changed:
            self._pause_save(after_img or before_img, vision, solver,
                           f"点击下一题后页面未变化（已等待{self.timing.get('max_page_change_wait', 3.0)}秒）")
            return StepResult()

        # 11. trace
        nscx, nscy = self.mapper.box_center_screen(vision.buttons.next.box)
        step_data = {
            "step": self.step + 1,
            "screenshot_img": screenshot,
            "page_state": vision.page_state,
            "question_type": vision.question_type,
            "question": vision.question_text,
            "options": opts_dict,
            "vision_confidence": {"text": vision.confidence.text, "layout": vision.confidence.layout},
            "vision_raw_json": vision.model_dump(),
            "solver_answer": solver.answer,
            "solver_confidence": solver.confidence,
            "solver_reason": solver.reason,
            "solver_raw_json": solver.model_dump(),
            "clicked_options": clicked,
            "next_button": {
                "box": vision.buttons.next.box,
                "image_center": [(vision.buttons.next.box[0] + vision.buttons.next.box[2]) // 2,
                                 (vision.buttons.next.box[1] + vision.buttons.next.box[3]) // 2],
                "screen_center": [nscx, nscy],
            },
            "page_changed": True,
            "error": None,
        }
        self.trace_logger.save_step(step_data)

        return StepResult(step_data=step_data)

    def _handle_loading(self, screenshot: Image.Image) -> StepResult:
        """处理 loading 状态"""
        for i in range(self.loading_retry_max):
            print(f"  页面 loading，等待 {self.loading_retry_delay}s 后重试 ({i+1}/{self.loading_retry_max})")
            time.sleep(self.loading_retry_delay)
            screenshot = capture_phone_screen(self.hwnd, self.viewport)
            vision = vision_parse(screenshot, self.vision_config)
            if vision.page_state != "loading":
                print(f"  页面状态变为: {vision.page_state}")
                # 不直接处理，让调用方重新走一次 process_one_step
                return StepResult()  # 返回空结果，外层会重新进入 process_one_step
        self._pause_save(screenshot, None, None, "页面持续 loading，请检查")
        return StepResult()

    def _handle_stop(self, result: StepResult):
        """处理停止"""
        reason = result.stop_reason
        print(f"\n[STOP] 停止原因: {reason}")
        if reason == "submit_detected":
            print("[INFO] 检测到交卷按钮，已停止自动操作。请手动接管。")
        self.trace_logger.save_stop(reason)
        self.trace_logger.session_dir.joinpath("FINAL_SCREENSHOT.png")
        try:
            img = capture_phone_screen(self.hwnd, self.viewport)
            img.save(self.trace_logger.session_dir / "FINAL_SCREENSHOT.png")
        except Exception:
            pass

    def _pause(self, reason: str):
        """暂停并等待用户指令"""
        print(f"\n[PAUSE] {reason}")
        print("  按 Enter 重试当前步骤 / 输入 'skip' 跳过 / 输入 'quit' 退出")
        choice = input("  > ").strip().lower()
        if choice == 'quit':
            raise FatalStopError(f"用户选择退出: {reason}")
        if choice == 'skip':
            self.step += 1
            return
        # 默认: 重试

    def _pause_save(self, screenshot, vision_result, solver_result, reason: str):
        """暂停并保存现场"""
        self.trace_logger.save_pause(
            self.step + 1, screenshot,
            vision_result.model_dump() if vision_result else {},
            solver_result.model_dump() if solver_result else None,
            reason,
        )
        self._pause(reason)
```

- [ ] **Step 2: Commit**

```bash
git add core/state_machine.py
git commit -m "feat: state_machine — 12步单题循环，安全硬编码检查点，三级异常处理"
```

---

### Task 13: 主入口 — `main.py`

依赖: Task 12

**Files:**
- Create: `main.py`

- [ ] **Step 1: 实现 main.py**

```python
"""ChaoxingAgent v1 — Windows 本地自动化答题工具

使用:
    uv run python main.py

流程:
    1. 输入进程名或 PID → 绑定窗口
    2. 手动框选手机画面区域
    3. 进入自动循环（截图→视觉解析→文本作答→点击→检测跳题）
    4. 遇到交卷按钮停止
"""

import json
import sys
from pathlib import Path

from core.window_selector import select as select_window_fn
from core.viewport_selector import select as select_viewport_fn
from core.state_machine import StateMachine
from core.errors import FatalStopError
from models.model_config import load_model_services


CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _load_or_create_config() -> dict:
    """加载 config.json，不存在则创建默认模板"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 不存在 → 先用默认模板
    template = {
        "target": {
            "process_name": "", "pid": None, "selected_hwnd": None,
            "window_title": "", "client_rect": [0, 0, 0, 0]
        },
        "viewport": {
            "lock_window_size_after_calibration": True,
            "phone_viewport_in_client": {"x": 0, "y": 0, "width": 0, "height": 0},
            "phone_viewport_ratio": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
        },
        "timing": {
            "between_multi_select_clicks": 0.2, "before_click_next": 0.2,
            "after_click_next": 0.5, "extra_wait_if_page_not_changed": 0.5,
            "max_page_change_wait": 3.0
        },
        "thresholds": {
            "vision_text_confidence": 0.75, "vision_layout_confidence": 0.75,
            "solver_confidence": 0.70, "page_change_pixel_ratio": 0.03,
            "window_size_change_ratio": 0.05
        },
        "page_change": {
            "compare_region_ratio": {"x1": 0.0, "y1": 0.08, "x2": 1.0, "y2": 0.75},
            "compare_resize": [200, 200]
        },
        "runtime": {
            "max_steps": 200, "stop_on_submit": True,
            "pause_on_popup": True, "pause_on_unknown": True,
            "save_trace": True, "loading_retry_max": 3,
            "loading_retry_delay": 1.0, "max_consecutive_errors": 3
        }
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    return template


def _save_config(config: dict):
    """保存配置到 config.json"""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _save_window_to_config(config: dict, win_info):
    """将窗口信息写入 config['target']"""
    config["target"] = {
        "process_name": win_info.process_name,
        "pid": win_info.pid,
        "selected_hwnd": win_info.hwnd,
        "window_title": win_info.window_title,
        "client_rect": list(win_info.client_rect),
    }
    _save_config(config)


def _save_viewport_to_config(config: dict, vp_info):
    """将 viewport 信息写入 config['viewport']"""
    config["viewport"] = {
        "lock_window_size_after_calibration": True,
        "phone_viewport_in_client": {
            "x": vp_info.x, "y": vp_info.y,
            "width": vp_info.width, "height": vp_info.height,
        },
        "phone_viewport_ratio": {
            "x": vp_info.ratio_x, "y": vp_info.ratio_y,
            "width": vp_info.ratio_w, "height": vp_info.ratio_h,
        },
    }
    _save_config(config)


def main():
    print("=" * 50)
    print("ChaoxingAgent v1")
    print("Windows 本地自动化答题工具")
    print("=" * 50)

    # 加载配置
    config = _load_or_create_config()
    model_services = load_model_services()

    # Step 1: 窗口绑定
    target = config.get("target", {})
    if target.get("selected_hwnd"):
        print(f"\n已有窗口绑定: hwnd={target['selected_hwnd']} title='{target.get('window_title','')}'")
        reuse = input("是否使用已有绑定？(y/n，n 则重新选择): ").strip().lower()
        if reuse != 'y':
            target = {}

    if not target.get("selected_hwnd"):
        user_input = input("\n请输入目标进程名或 PID: ").strip()
        if not user_input:
            print("未输入，退出。")
            return
        win_info = select_window_fn(user_input)
        _save_window_to_config(config, win_info)
        target = config["target"]

    # Step 2: 手机画面区域标定
    viewport = config.get("viewport", {})
    vp_in_client = viewport.get("phone_viewport_in_client", {})
    if vp_in_client.get("width", 0) > 0:
        print(f"\n已标定区域: {vp_in_client}")
        recal = input("是否使用已有标定？(y/n，n 则重新标定): ").strip().lower()
        if recal != 'y':
            viewport = {}

    if not viewport.get("phone_viewport_in_client", {}).get("width", 0):
        # 需要临时构造 WindowInfo 用于截图
        from core.window_selector import WindowInfo
        win_info = WindowInfo(
            hwnd=target["selected_hwnd"],
            pid=target["pid"],
            process_name=target["process_name"],
            window_title=target.get("window_title", ""),
            client_rect=tuple(target.get("client_rect", [0, 0, 0, 0])),
            screen_rect=tuple(target.get("client_rect", [0, 0, 0, 0])),
            width=target["client_rect"][2] - target["client_rect"][0] if len(target.get("client_rect", [])) == 4 else 0,
            height=target["client_rect"][3] - target["client_rect"][1] if len(target.get("client_rect", [])) == 4 else 0,
        )
        vp_info = select_viewport_fn(win_info)
        _save_viewport_to_config(config, vp_info)

    # 重新加载最新配置
    config = _load_or_create_config()

    # Step 3: 启动状态机
    print("\n" + "=" * 50)
    try:
        sm = StateMachine(config, model_services)
        sm.run()
    except FatalStopError as e:
        print(f"\n[FATAL] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] 用户中断")
    except Exception as e:
        print(f"\n[FATAL] 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: main — CLI 入口，窗口绑定/标定/状态机启动流程"
```

---

### Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
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
# 1. 克隆
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

```
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README"
```

---

## 验证流程

### 端到端验证步骤

1. **打开投屏软件**（如 vivoScreen），确认窗口可见
2. **运行程序**: `uv run python main.py`
3. **输入进程名**: 如 `vivoScreen.exe`
4. **选择窗口**: 多窗口时选择手机画面所在窗口
5. **框选手机画面**: 拖拽鼠标选中手机画面区域，按 Enter 确认
6. **观察循环**: 程序开始截图 → 调用视觉模型 → 调用文本模型 → 点击 → 检测跳题
7. **到达最后一题**: 出现交卷按钮 → 程序停止并提示
8. **检查 trace 目录**: `trace/session_xxx/` 下有截图和 JSON

### 单模块验证（独立测试）

```bash
# 窗口选择
uv run python -c "from core.window_selector import select; w=select('notepad.exe'); print(w)"

# 截图
uv run python -c "from core.window_selector import select; from core.screen_capture import capture_client_area; w=select('notepad.exe'); img=capture_client_area(w.hwnd); img.save('test.png')"

# 坐标映射
uv run python -c "from core.coordinate_mapper import CoordinateMapper; m=CoordinateMapper(198742, {'phone_viewport_in_client':{'x':0,'y':0,'width':400,'height':800}}); print(m.image_to_screen(200,400))"

# 页面变化检测
uv run python -c "from PIL import Image; import numpy as np; from core.page_change_detector import detect; a=Image.fromarray(np.random.randint(0,256,(200,200,3),dtype=np.uint8)); b=Image.fromarray(np.random.randint(0,256,(200,200,3),dtype=np.uint8)); print(detect(a,b,{'x1':0,'y1':0,'x2':1,'y2':1},0.03))"

# trace 日志
uv run python -c "from core.trace_logger import TraceLogger; from PIL import Image; t=TraceLogger(); t.save_step({'step':1,'screenshot_img':Image.new('RGB',(100,100),'red'),'page_state':'question','error':None})"
```

---

> **实施计划结束**。按 Task 0 → 14 顺序执行，每完成一个 Task 做一次 commit。
