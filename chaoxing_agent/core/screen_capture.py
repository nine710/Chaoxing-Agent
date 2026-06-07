"""窗口截图 — 截取客户区 / 裁剪手机画面"""

import win32con
import win32gui
import win32ui
from PIL import Image


def capture_client_area(hwnd: int) -> Image.Image:
    """截取窗口客户区，返回 PIL Image (RGB)"""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise RuntimeError(f"窗口客户区尺寸无效: {width}x{height}")

    hwnd_dc = None
    mfc_dc = None
    save_dc = None
    bitmap = None

    try:
        hwnd_dc = win32gui.GetDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        return Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bits,
            "raw",
            "BGRX",
            0,
            1,
        )
    finally:
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if save_dc is not None:
            save_dc.DeleteDC()
        if mfc_dc is not None:
            mfc_dc.DeleteDC()
        if hwnd_dc is not None:
            win32gui.ReleaseDC(hwnd, hwnd_dc)


def capture_phone_screen(hwnd: int, viewport: dict) -> Image.Image:
    """截取手机画面区域 (根据 viewport 裁剪)"""
    full = capture_client_area(hwnd)
    vp = viewport["phone_viewport_in_client"]
    x, y, w, h = vp["x"], vp["y"], vp["width"], vp["height"]
    return full.crop((x, y, x + w, y + h))


def check_window_alive(hwnd: int) -> bool:
    """检查窗口是否仍然存在"""
    try:
        return win32gui.IsWindow(hwnd) != 0
    except Exception:
        return False


def check_window_size_unchanged(hwnd: int, expected_client_rect: tuple, max_ratio: float = 0.05) -> bool:
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
