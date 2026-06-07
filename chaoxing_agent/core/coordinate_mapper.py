"""坐标映射 — 手机截图像素坐标 ↔ Windows 屏幕坐标"""

import win32gui


class CoordinateMapper:
    """将手机截图内的像素坐标转换为 Windows 屏幕绝对坐标"""

    def __init__(self, hwnd: int, viewport: dict):
        self.hwnd = hwnd

        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (cl, ct))
        self.client_screen_left = pt[0]
        self.client_screen_top = pt[1]

        vp = viewport["phone_viewport_in_client"]
        self.vp_x = vp["x"]
        self.vp_y = vp["y"]

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
