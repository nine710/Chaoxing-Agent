"""页面变化检测 — 灰度差异判断题目是否跳转"""

import time
from typing import Callable, Optional

import numpy as np
from PIL import Image


def _crop_question_region(img: Image.Image, region: dict, resize: tuple[int, int] = (200, 200)) -> np.ndarray:
    """裁剪题目区域 → 灰度 → 缩放"""
    w, h = img.size
    x1 = int(w * region["x1"])
    y1 = int(h * region["y1"])
    x2 = int(w * region["x2"])
    y2 = int(h * region["y2"])

    cropped = img.crop((x1, y1, x2, y2))
    gray = cropped.convert("L")
    resized = gray.resize(resize, Image.LANCZOS)
    return np.array(resized, dtype=np.float32)


def detect(before: Image.Image, after: Image.Image, region: dict, threshold: float, _resize: tuple = (200, 200)) -> tuple[bool, float]:
    """比较两张截图的题目区域差异"""
    before_arr = _crop_question_region(before, region, _resize)
    after_arr = _crop_question_region(after, region, _resize)

    diff = np.abs(before_arr - after_arr) / 255.0
    changed_ratio = float(np.mean(diff > 0.1))
    return changed_ratio > threshold, changed_ratio


def wait_for_change(before: Image.Image, capture_fn: Callable[[], Image.Image], config: dict) -> tuple[bool, Optional[Image.Image]]:
    """等待页面变化，最多等到 max_page_change_wait 秒。"""
    page_change_cfg = config.get("page_change", {})
    timing = config.get("timing", {})
    thresholds = config.get("thresholds", {})

    region = page_change_cfg.get("compare_region_ratio", {"x1": 0.0, "y1": 0.08, "x2": 1.0, "y2": 0.75})
    resize = tuple(page_change_cfg.get("compare_resize", [200, 200]))
    threshold = thresholds.get("page_change_pixel_ratio", 0.03)
    extra_wait = timing.get("extra_wait_if_page_not_changed", 0.5)
    max_wait = timing.get("max_page_change_wait", 3.0)

    after = capture_fn()
    changed, ratio = detect(before, after, region, threshold, resize)
    print(f"  页面变化检测: ratio={ratio:.4f} threshold={threshold} changed={changed}")
    if changed:
        return True, after

    elapsed = timing.get("after_click_next", 0.5)
    while elapsed < max_wait:
        time.sleep(extra_wait)
        elapsed += extra_wait
        after = capture_fn()
        changed, ratio = detect(before, after, region, threshold, resize)
        print(f"  重试检测 ({elapsed:.1f}s): ratio={ratio:.4f} changed={changed}")
        if changed:
            return True, after

    return False, after
