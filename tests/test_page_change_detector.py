"""page_change_detector 的回归测试。"""

import time
from PIL import Image

import numpy as np

from chaoxing_agent.core.page_change_detector import _crop_question_region, detect, wait_for_change


def _make_img(seed: int = 0, size=(400, 800)) -> Image.Image:
    """生成带噪声的灰度图（seed 不同则内容不同）。"""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(size[1], size[0]), dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_crop_question_region_returns_2d_array():
    img = _make_img(seed=1)
    region = {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
    arr = _crop_question_region(img, region, resize=(100, 200))
    assert arr.shape == (200, 100)
    assert arr.dtype == np.float32
    assert arr.min() >= 0 and arr.max() <= 255


def test_crop_question_region_partial():
    img = _make_img(seed=1, size=(400, 800))
    region = {"x1": 0.0, "y1": 0.1, "x2": 1.0, "y2": 0.5}
    arr = _crop_question_region(img, region, resize=(50, 50))
    assert arr.shape == (50, 50)


def test_detect_identical_images_no_change():
    img = _make_img(seed=2)
    changed, ratio = detect(img, img.copy(), {"x1": 0, "y1": 0, "x2": 1, "y2": 1}, threshold=0.03)
    assert changed is False
    assert ratio < 0.001


def test_detect_completely_different_changes():
    a = _make_img(seed=1)
    b = _make_img(seed=99)
    changed, ratio = detect(a, b, {"x1": 0, "y1": 0, "x2": 1, "y2": 1}, threshold=0.03)
    assert changed is True
    assert ratio > 0.3


def test_detect_threshold_triggers_above():
    """刚好超过阈值的差异应被识别。"""
    a = np.zeros((100, 100), dtype=np.uint8)
    b = np.zeros((100, 100), dtype=np.uint8)
    b[0:30, 0:100] = 255  # 30% 像素差异
    img_a = Image.fromarray(a, mode="L")
    img_b = Image.fromarray(b, mode="L")
    changed, ratio = detect(img_a, img_b, {"x1": 0, "y1": 0, "x2": 1, "y2": 1}, threshold=0.03)
    assert changed is True


def test_wait_for_change_returns_true_on_first_try(monkeypatch):
    monkeypatch.setattr("chaoxing_agent.core.page_change_detector.time.sleep", lambda *_: None)
    before = _make_img(seed=1)
    after = _make_img(seed=99)

    captured = {"n": 0}
    def cap():
        captured["n"] += 1
        return after

    cfg = {
        "page_change": {"compare_region_ratio": {"x1": 0, "y1": 0, "x2": 1, "y2": 1}, "compare_resize": [100, 100]},
        "timing": {"extra_wait_if_page_not_changed": 0.5, "max_page_change_wait": 3.0, "after_click_next": 0.5},
        "thresholds": {"page_change_pixel_ratio": 0.03},
    }
    changed, latest = wait_for_change(before, cap, cfg)
    assert changed is True
    assert latest is after
    assert captured["n"] == 1  # 一次成功


def test_wait_for_change_returns_false_when_no_change(monkeypatch):
    monkeypatch.setattr("chaoxing_agent.core.page_change_detector.time.sleep", lambda *_: None)
    same = _make_img(seed=1)
    captured = {"n": 0}
    def cap():
        captured["n"] += 1
        return same.copy()

    cfg = {
        "page_change": {"compare_region_ratio": {"x1": 0, "y1": 0, "x2": 1, "y2": 1}, "compare_resize": [100, 100]},
        "timing": {"extra_wait_if_page_not_changed": 0.5, "max_page_change_wait": 3.0, "after_click_next": 0.5},
        "thresholds": {"page_change_pixel_ratio": 0.03},
    }
    changed, latest = wait_for_change(same, cap, cfg)
    assert changed is False
    # 第一次 + 后续重试（max_wait=3.0, extra=0.5 → 至少 6 次截图）
    assert captured["n"] >= 2
