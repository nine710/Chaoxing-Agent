"""窗口选择器 — 根据 PID/进程名 找到并绑定 Windows 窗口"""

from dataclasses import dataclass
from typing import Optional

import psutil
import win32gui
import win32process


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

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width < 100 or height < 100:
        return None

    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
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


def find_processes_by_name(name: str) -> list[psutil.Process]:
    """根据进程名查找所有匹配进程"""
    name_lower = name.lower().removesuffix(".exe")
    matches = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc_name = proc.info["name"]
            if proc_name and name_lower in proc_name.lower().removesuffix(".exe"):
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matches


def find_process_by_pid(pid: int) -> Optional[psutil.Process]:
    """根据 PID 查找进程"""
    try:
        return psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None


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
                info = _get_window_info(hwnd, pid, proc.name())
                if info:
                    results.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


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
        print(f"\n绑定窗口: hwnd={w.hwnd} title='{w.window_title}' rect={w.client_rect} size={w.width}x{w.height}")
        return w

    print(f"\nPID={proc.pid} 下有 {len(windows)} 个可见窗口:")
    for i, w in enumerate(windows, 1):
        print(f"  [{i}] hwnd={w.hwnd} title='{w.window_title}' rect={w.client_rect} size={w.width}x{w.height}")

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
