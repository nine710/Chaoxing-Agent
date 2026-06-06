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

from core.errors import FatalStopError
from core.state_machine import StateMachine
from core.viewport_selector import select as select_viewport_fn
from core.window_selector import select as select_window_fn
from models.model_config import load_model_services


CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _default_config() -> dict:
    """返回默认 config.json 模板。"""
    return {
        "target": {
            "process_name": "",
            "pid": None,
            "selected_hwnd": None,
            "window_title": "",
            "client_rect": [0, 0, 0, 0],
        },
        "viewport": {
            "lock_window_size_after_calibration": True,
            "phone_viewport_in_client": {"x": 0, "y": 0, "width": 0, "height": 0},
            "phone_viewport_ratio": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
        },
        "timing": {
            "between_multi_select_clicks": 0.2,
            "before_click_next": 0.2,
            "after_click_next": 0.5,
            "extra_wait_if_page_not_changed": 0.5,
            "max_page_change_wait": 3.0,
        },
        "thresholds": {
            "vision_text_confidence": 0.75,
            "vision_layout_confidence": 0.75,
            "solver_confidence": 0.70,
            "page_change_pixel_ratio": 0.03,
            "window_size_change_ratio": 0.05,
        },
        "page_change": {
            "compare_region_ratio": {"x1": 0.0, "y1": 0.08, "x2": 1.0, "y2": 0.75},
            "compare_resize": [200, 200],
        },
        "runtime": {
            "max_steps": 200,
            "stop_on_submit": True,
            "pause_on_popup": True,
            "pause_on_unknown": True,
            "save_trace": True,
            "loading_retry_max": 3,
            "loading_retry_delay": 1.0,
            "max_consecutive_errors": 3,
        },
    }


def _load_or_create_config() -> dict:
    """加载 config.json，不存在则创建默认模板。"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    template = _default_config()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    return template


def _save_config(config: dict):
    """保存配置到 config.json。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _save_window_to_config(config: dict, win_info):
    """将窗口信息写入 config['target']。"""
    config["target"] = {
        "process_name": win_info.process_name,
        "pid": win_info.pid,
        "selected_hwnd": win_info.hwnd,
        "window_title": win_info.window_title,
        "client_rect": list(win_info.client_rect),
    }
    _save_config(config)


def _save_viewport_to_config(config: dict, vp_info):
    """将 viewport 信息写入 config['viewport']。"""
    config["viewport"] = {
        "lock_window_size_after_calibration": True,
        "phone_viewport_in_client": {
            "x": vp_info.x,
            "y": vp_info.y,
            "width": vp_info.width,
            "height": vp_info.height,
        },
        "phone_viewport_ratio": {
            "x": vp_info.ratio_x,
            "y": vp_info.ratio_y,
            "width": vp_info.ratio_w,
            "height": vp_info.ratio_h,
        },
    }
    _save_config(config)


def main():
    print("=" * 50)
    print("ChaoxingAgent v1")
    print("Windows 本地自动化答题工具")
    print("=" * 50)

    config = _load_or_create_config()
    model_services = load_model_services()

    target = config.get("target", {})
    if target.get("selected_hwnd"):
        print(f"\n已有窗口绑定: hwnd={target['selected_hwnd']} title='{target.get('window_title', '')}'")
        reuse = input("是否使用已有绑定？(y/n，n 则重新选择): ").strip().lower()
        if reuse != "y":
            target = {}

    if not target.get("selected_hwnd"):
        user_input = input("\n请输入目标进程名或 PID: ").strip()
        if not user_input:
            print("未输入，退出。")
            return
        win_info = select_window_fn(user_input)
        _save_window_to_config(config, win_info)
        target = config["target"]

    viewport = config.get("viewport", {})
    vp_in_client = viewport.get("phone_viewport_in_client", {})
    if vp_in_client.get("width", 0) > 0:
        print(f"\n已标定区域: {vp_in_client}")
        recal = input("是否使用已有标定？(y/n，n 则重新标定): ").strip().lower()
        if recal != "y":
            viewport = {}

    if not viewport.get("phone_viewport_in_client", {}).get("width", 0):
        from core.window_selector import WindowInfo

        client_rect = target.get("client_rect", [0, 0, 0, 0])
        win_info = WindowInfo(
            hwnd=target["selected_hwnd"],
            pid=target["pid"],
            process_name=target["process_name"],
            window_title=target.get("window_title", ""),
            client_rect=tuple(client_rect),
            screen_rect=tuple(client_rect),
            width=client_rect[2] - client_rect[0] if len(client_rect) == 4 else 0,
            height=client_rect[3] - client_rect[1] if len(client_rect) == 4 else 0,
        )
        vp_info = select_viewport_fn(win_info)
        _save_viewport_to_config(config, vp_info)

    config = _load_or_create_config()

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
