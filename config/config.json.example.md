# config.json.example — 运行时配置示例

`config.json.example` 严格 JSON（无注释），与本文件配套阅读。
真实配置文件 `config.json` 已被 `.gitignore` 排除；首次运行 `main.py` 时会自动从 example 复制生成。

## 字段说明

### `target` — 目标应用进程设置（**用户在 config.json 里直接设置**）

> 旧版需要在程序里交互式输入"进程名或 PID"，新版本**预填在 config.json** 即可，程序启动时直接绑定。

| 字段 | 类型 | 说明 |
|------|------|------|
| `process_name` | str | 目标进程名（不含 `.exe` 后缀也可），如 `"vivoScreen"` |
| `pid` | int \| null | 进程 PID（更精确） |
| `selected_hwnd` | int \| null | 窗口句柄（可选；运行时会自动按 PID 解析到顶层可见窗口并回填） |
| `window_title` | str | 窗口标题（运行期回填） |
| `client_rect` | `[l, t, r, b]` | 客户区屏幕绝对坐标（运行期回填） |

**最少配置示例**（写入 `config/config.json`）：

```json
{
  "target": {
    "process_name": "vivoScreen",
    "pid": null,
    "selected_hwnd": null,
    "window_title": "",
    "client_rect": [0, 0, 0, 0]
  }
}
```

或者只填 `pid`（更精确）：

```json
{
  "target": {
    "process_name": "",
    "pid": 12345,
    "selected_hwnd": null,
    "window_title": "",
    "client_rect": [0, 0, 0, 0]
  }
}
```

`process_name` 与 `pid` 都不填时，程序退回交互式提示你输入。
启动后程序会用这里填的 `process_name` 或 `pid` 找到顶层可见窗口，并把 `selected_hwnd` / `window_title` / `client_rect` 回写（`lock_window_size_after_calibration=true` 时若尺寸漂移 >5% 会暂停）。

**完整 JSON 模板（可直接复制覆盖 `config/config.json`）**：

```json
{
  "target": {
    "process_name": "vivoScreen",
    "pid": null,
    "selected_hwnd": null,
    "window_title": "",
    "client_rect": [0, 0, 0, 0]
  },
  "viewport": {
    "lock_window_size_after_calibration": true,
    "phone_viewport_in_client": {"x": 0, "y": 0, "width": 0, "height": 0},
    "phone_viewport_ratio":    {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
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
    "compare_region_ratio": {"x1": 0.0, "y1": 0.08, "x2": 1.0, "y2": 0.75},
    "compare_resize": [200, 200]
  },
  "runtime": {
    "max_steps": 200,
    "pause_on_popup": true,
    "pause_on_unknown": true,
    "save_trace": true,
    "loading_retry_max": 3,
    "loading_retry_delay": 1.0,
    "max_consecutive_errors": 3
  }
}
```

把 `"vivoScreen"` 改成你要控制的投屏/远程应用进程名（Windows 任务管理器可看），保存后 `uv run python main.py` 启动即直接绑定该进程顶层窗口，不再走交互式选择。

### `viewport` — 手机画面区域（标定后写入）

| 字段 | 说明 |
|------|------|
| `lock_window_size_after_calibration` | 标定后锁定窗口尺寸，尺寸变化 >5% 触发暂停 |
| `phone_viewport_in_client.x/y/width/height` | 相对客户区的像素坐标 |
| `phone_viewport_ratio.x/y/width/height` | 0~1 比例（窗口缩放时使用） |

### `timing` — 时序参数

| 键 | 默认 | 说明 |
|----|------|------|
| `between_multi_select_clicks` | 0.2 | 多选题两个选项之间的点击间隔 |
| `before_click_next` | 0.2 | 点击下一题按钮前的等待 |
| `after_click_next` | 0.5 | 点击下一题按钮后的等待 |
| `extra_wait_if_page_not_changed` | 0.5 | 页面未变化时单次重试间隔 |
| `max_page_change_wait` | 3.0 | 页面未变化的最大等待时间 |

### `thresholds` — 阈值

| 键 | 默认 | 说明 |
|----|------|------|
| `vision_text_confidence` | 0.75 | 视觉文字识别置信度下限，低于此值暂停 |
| `vision_layout_confidence` | 0.75 | 视觉布局识别置信度下限 |
| `solver_confidence` | 0.70 | 文本模型置信度下限 |
| `page_change_pixel_ratio` | 0.03 | 页面变化像素比阈值 |
| `window_size_change_ratio` | 0.05 | 窗口尺寸变化比例上限（>此值暂停） |

### `page_change` — 页面变化检测

| 键 | 说明 |
|----|------|
| `compare_region_ratio.{x1,y1,x2,y2}` | 题目区域占整图的比例，灰度对比只取这个范围 |
| `compare_resize` | 对比前缩放到 `[w, h]`，减少光照和小位移影响 |

### `runtime` — 运行时控制

| 键 | 默认 | 说明 |
|----|------|------|
| `max_steps` | 200 | 最大连续题数 |
| `pause_on_popup` | true | 弹窗检测到时暂停 |
| `pause_on_unknown` | true | 未知页面状态时暂停 |
| `save_trace` | true | 是否落 trace |
| `loading_retry_max` | 3 | loading 状态重试次数 |
| `loading_retry_delay` | 1.0 | loading 重试间隔（秒） |
| `max_consecutive_errors` | 3 | 连续 RecoverableError 上限 |

## 初始化

```bash
# 首次运行会自动从 example 复制生成 config.json：
uv run python main.py

# 或显式重新生成（覆盖现有 config.json）：
uv run python main.py --init-config
```

## 不通过 .env 覆盖

按项目规范，`config.json` 的可调字段**不**通过 `.env`/环境变量覆盖。如需修改请直接编辑 `config.json`。
