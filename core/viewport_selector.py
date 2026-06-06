"""手机画面区域选择 — tkinter ROI 框选"""

from dataclasses import dataclass
from typing import Optional
import tkinter as tk

from PIL import Image, ImageTk

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
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline="red",
            width=2,
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        pass

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
            return

        self.result = ViewportInfo(
            x=x,
            y=y,
            width=w,
            height=h,
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
    print("\n手机画面区域 (相对客户区像素):")
    print(f"  x={vp.x} y={vp.y} width={vp.width} height={vp.height}")
    print("比例坐标:")
    print(f"  ratio_x={vp.ratio_x:.4f} ratio_y={vp.ratio_y:.4f} ratio_w={vp.ratio_w:.4f} ratio_h={vp.ratio_h:.4f}")
    return vp
