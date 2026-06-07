"""click_executor 的回归测试。"""

from unittest.mock import MagicMock, patch

import pytest

from chaoxing_agent.core import click_executor
from chaoxing_agent.core.click_executor import click_at, click_options, click_next_button
from schemas.vision_schema import VisionOption


def _make_options(*keys):
    return [
        VisionOption(key=k, text=f"选项{k}", box=[0, 100 * i, 100, 100 * i + 50])
        for i, k in enumerate(keys)
    ]


def test_click_options_raises_on_unknown_answer_key():
    """click_options 收到不在 options 里的 key 时应明确报错（而不是 KeyError 隐式）。"""
    options = _make_options("A", "B")
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (100, 200)
    timing = {"between_multi_select_clicks": 0.0}

    with patch.object(click_executor, "click_at"):
        with pytest.raises(KeyError):
            click_options(["X"], options, mapper, timing)


def test_click_options_clicks_each_in_order(monkeypatch):
    options = _make_options("A", "B", "C")
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (100, 200)
    timing = {"between_multi_select_clicks": 0.0}

    click_calls = []
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: click_calls.append((x, y)))

    click_options(["A", "C"], options, mapper, timing)
    assert click_calls == [(100, 200), (100, 200)]


def test_click_options_no_sleep_after_last():
    """多选时，最后一个选项点击后不应再 sleep。"""
    options = _make_options("A", "B", "C")
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (0, 0)
    timing = {"between_multi_select_clicks": 0.0}

    monkeypatch = pytest.MonkeyPatch()
    sleep_calls = []
    monkeypatch.setattr(click_executor.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: None)

    click_options(["A", "B", "C"], options, mapper, timing)
    # 3 个选项 → 期望 2 次 sleep (在 A->B 之间, B->C 之间)，不是 3 次
    assert len(sleep_calls) == 2
    monkeypatch.undo()


def test_click_options_single_answer_no_sleep():
    options = _make_options("A")
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (0, 0)
    timing = {"between_multi_select_clicks": 0.5}

    monkeypatch = pytest.MonkeyPatch()
    sleep_calls = []
    monkeypatch.setattr(click_executor.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: None)

    click_options(["A"], options, mapper, timing)
    # 单选 → 0 次 sleep
    assert sleep_calls == []
    monkeypatch.undo()


def test_click_options_refreshes_mapper_before_each_click(monkeypatch):
    """窗口可能在模型调用/多选间隔期间移动；每次选项点击前都要重新计算窗口位置。"""
    options = _make_options("A", "B")
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (10, 20)
    monkeypatch.setattr(click_executor.time, "sleep", lambda s: None)
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: None)

    click_options(["A", "B"], options, mapper, {"between_multi_select_clicks": 0.0})

    assert mapper.refresh.call_count == 2
    assert mapper.method_calls[0][0] == "refresh"
    assert mapper.method_calls[1][0] == "box_center_screen"


def test_click_next_button_refreshes_after_before_wait(monkeypatch):
    """下一题点击前有 before_click_next 等待；等待期间移动窗口也必须刷新 mapper。"""
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (50, 60)
    calls = []
    monkeypatch.setattr(click_executor.time, "sleep", lambda s: calls.append(("sleep", s)))
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: calls.append(("click", x, y)))

    click_next_button([0, 0, 100, 50], mapper, {"before_click_next": 0.1, "after_click_next": 0.3})

    assert mapper.refresh.call_count == 1
    assert calls == [("sleep", 0.1), ("click", 50, 60), ("sleep", 0.3)]


def test_click_next_button_waits_before_and_after(monkeypatch):
    """click_next_button 前后各 sleep 一次。"""
    mapper = MagicMock()
    mapper.box_center_screen.return_value = (50, 60)
    timing = {"before_click_next": 0.1, "after_click_next": 0.3}

    sleep_calls = []
    click_calls = []
    monkeypatch.setattr(click_executor.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(click_executor, "click_at", lambda x, y: click_calls.append((x, y)))

    click_next_button([0, 0, 100, 50], mapper, timing)
    assert sleep_calls == [0.1, 0.3]
    assert click_calls == [(50, 60)]


def test_to_screen_coords_normalizes_to_0_65535(monkeypatch):
    """_to_screen_coords 应把屏幕坐标归一化到 [0, 65535]。"""
    def fake_get(idx):
        return {76: 0, 77: 0, 78: 1920, 79: 1080}[idx]

    monkeypatch.setattr(click_executor.ctypes.windll.user32, "GetSystemMetrics",
                        lambda idx: fake_get(idx))
    nx, ny = click_executor._to_screen_coords(960, 540)
    assert 0 <= nx <= 65535
    assert 0 <= ny <= 65535
    # 中点应大致在中点 (≈32767)
    assert 32000 < nx < 33500
    assert 32000 < ny < 33500


def test_to_screen_coords_raises_on_zero_virtual_screen(monkeypatch):
    """虚拟屏幕 width/height <= 1 时应报错。"""
    monkeypatch.setattr(click_executor.ctypes.windll.user32, "GetSystemMetrics", lambda idx: 0)
    with pytest.raises(RuntimeError, match="虚拟屏幕尺寸无效"):
        click_executor._to_screen_coords(100, 100)
