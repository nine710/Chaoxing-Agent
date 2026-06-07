"""coordinate_mapper 的回归测试。"""

from unittest.mock import patch

import pytest

from chaoxing_agent.core.coordinate_mapper import CoordinateMapper


def _make_mapper(hwnd, client_screen_left, client_screen_top, vp_x, vp_y):
    """构造时不真正调 win32gui —— mock。"""
    with patch("chaoxing_agent.core.coordinate_mapper.win32gui.GetClientRect", return_value=(0, 0, 388, 928)), \
         patch("chaoxing_agent.core.coordinate_mapper.win32gui.ClientToScreen", return_value=(client_screen_left, client_screen_top)):
        return CoordinateMapper(hwnd, {
            "phone_viewport_in_client": {"x": vp_x, "y": vp_y, "width": 0, "height": 0},
        })


def test_init_computes_phone_origin_from_viewport():
    m = _make_mapper(hwnd=12345, client_screen_left=2009, client_screen_top=168, vp_x=3, vp_y=31)
    assert m._phone_left == 2012
    assert m._phone_top == 199


def test_image_to_screen_adds_viewport_offset():
    m = _make_mapper(hwnd=12345, client_screen_left=2000, client_screen_top=100, vp_x=10, vp_y=20)
    sx, sy = m.image_to_screen(50, 80)
    assert (sx, sy) == (2060, 200)


def test_box_center_screen_rounds_toward_zero():
    m = _make_mapper(hwnd=12345, client_screen_left=0, client_screen_top=0, vp_x=0, vp_y=0)
    # 奇数尺寸 → 整数除法截断
    sx, sy = m.box_center_screen([1, 2, 4, 7])  # cx=(1+4)//2=2, cy=(2+7)//2=4
    assert (sx, sy) == (2, 4)


def test_box_center_screen_large_box():
    m = _make_mapper(hwnd=12345, client_screen_left=100, client_screen_top=200, vp_x=5, vp_y=10)
    # box=[0,0,381,841] → center=(190, 420) → screen=(100+5+190, 200+10+420)=(295, 630)
    sx, sy = m.box_center_screen([0, 0, 381, 841])
    assert (sx, sy) == (295, 630)


def test_refresh_picks_up_window_movement():
    m = _make_mapper(hwnd=12345, client_screen_left=0, client_screen_top=0, vp_x=10, vp_y=10)
    # 窗口被拖到 (500, 600)
    with patch("chaoxing_agent.core.coordinate_mapper.win32gui.GetClientRect", return_value=(0, 0, 388, 928)), \
         patch("chaoxing_agent.core.coordinate_mapper.win32gui.ClientToScreen", return_value=(500, 600)):
        m.refresh()
    sx, sy = m.image_to_screen(0, 0)
    assert (sx, sy) == (510, 610)
