"""鼠标点击执行器 — 使用 ctypes + SendInput"""

import ctypes
import time
from ctypes import wintypes

from core.coordinate_mapper import CoordinateMapper

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


def _to_screen_coords(x: int, y: int) -> tuple[int, int]:
    """像素坐标 → 虚拟屏幕归一化坐标 (0~65535)。"""
    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

    if width <= 1 or height <= 1:
        raise RuntimeError(f"虚拟屏幕尺寸无效: {width}x{height}")

    nx = int((x - left) * 65535 / (width - 1))
    ny = int((y - top) * 65535 / (height - 1))
    return nx, ny


def _send_input(event: INPUT):
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def click_at(x: int, y: int):
    """在屏幕坐标 (x, y) 执行鼠标左键点击（使用 SendInput）。"""
    nx, ny = _to_screen_coords(x, y)

    down = INPUT()
    down.type = INPUT_MOUSE
    down.union.mi.dx = nx
    down.union.mi.dy = ny
    down.union.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN

    up = INPUT()
    up.type = INPUT_MOUSE
    up.union.mi.dx = nx
    up.union.mi.dy = ny
    up.union.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTUP

    _send_input(down)
    time.sleep(0.02)
    _send_input(up)


def click_options(answers: list[str], options: list, mapper: CoordinateMapper, timing: dict):
    """根据答案 key 依次点击对应选项。"""
    option_map = {opt.key: opt for opt in options}

    for i, answer_key in enumerate(answers):
        opt = option_map[answer_key]
        sx, sy = mapper.box_center_screen(opt.box)
        print(f"  [点击选项 {answer_key}] 截图坐标: {opt.box} → 屏幕坐标: ({sx}, {sy})")
        click_at(sx, sy)

        if len(answers) > 1 and i < len(answers) - 1:
            time.sleep(timing.get("between_multi_select_clicks", 0.2))


def click_next_button(box: list[int], mapper: CoordinateMapper, timing: dict):
    """点击下一题按钮（含前后等待）"""
    time.sleep(timing.get("before_click_next", 0.2))
    sx, sy = mapper.box_center_screen(box)
    print(f"  [点击下一题] 截图坐标: {box} → 屏幕坐标: ({sx}, {sy})")
    click_at(sx, sy)
    time.sleep(timing.get("after_click_next", 0.5))
