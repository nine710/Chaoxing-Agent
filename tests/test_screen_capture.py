"""screen_capture 的回归测试。"""

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from chaoxing_agent.core import screen_capture as sc


def test_check_window_alive_returns_true_for_valid(monkeypatch):
    monkeypatch.setattr(sc.win32gui, "IsWindow", lambda h: 1)
    assert sc.check_window_alive(12345) is True


def test_check_window_alive_returns_false_on_exception(monkeypatch):
    def boom(_):
        raise RuntimeError("win32 broken")
    monkeypatch.setattr(sc.win32gui, "IsWindow", boom)
    assert sc.check_window_alive(12345) is False


def test_check_window_size_unchanged_no_change(monkeypatch):
    monkeypatch.setattr(sc.win32gui, "GetClientRect", lambda h: (0, 0, 388, 928))
    expected = (0, 0, 388, 928)
    assert sc.check_window_size_unchanged(12345, expected, 0.05) is True


def test_check_window_size_unchanged_size_grew_5pct(monkeypatch):
    """宽变化刚好 5% 时不算超过阈值（<=）。"""
    monkeypatch.setattr(sc.win32gui, "GetClientRect", lambda h: (0, 0, 407, 928))  # 388 → 407 (+4.9%)
    expected = (0, 0, 388, 928)
    assert sc.check_window_size_unchanged(12345, expected, 0.05) is True


def test_check_window_size_unchanged_size_grew_6pct(monkeypatch):
    """宽变化 >5% 时应返回 False（需要重新标定）。"""
    monkeypatch.setattr(sc.win32gui, "GetClientRect", lambda h: (0, 0, 412, 928))  # +6.2%
    expected = (0, 0, 388, 928)
    assert sc.check_window_size_unchanged(12345, expected, 0.05) is False


def test_check_window_size_unchanged_zero_expected_returns_true(monkeypatch):
    """expected 尺寸为 0 时不应触发"尺寸变化"判断（避免除零）。"""
    monkeypatch.setattr(sc.win32gui, "GetClientRect", lambda h: (0, 0, 388, 928))
    assert sc.check_window_size_unchanged(12345, (0, 0, 0, 0), 0.05) is True


def test_capture_client_area_raises_on_zero_size(monkeypatch):
    monkeypatch.setattr(sc.win32gui, "GetClientRect", lambda h: (0, 0, 0, 0))
    with pytest.raises(RuntimeError, match="客户区尺寸无效"):
        sc.capture_client_area(12345)


def test_capture_phone_screen_crops_correctly(monkeypatch):
    """capture_phone_screen 应先截全客户区再 crop viewport。"""
    fake_img = Image.new("RGB", (400, 900), (255, 0, 0))
    monkeypatch.setattr(sc, "capture_client_area", lambda h: fake_img.copy())

    viewport = {"phone_viewport_in_client": {"x": 10, "y": 20, "width": 100, "height": 50}}
    out = sc.capture_phone_screen(12345, viewport)
    assert out.size == (100, 50)
    # crop 区域应来自 (10,20) 起 100x50
    assert out.getpixel((0, 0)) == (255, 0, 0)
