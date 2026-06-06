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
