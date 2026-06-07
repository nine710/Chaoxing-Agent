"""state_machine 关键安全边界的回归测试。

不做完整 e2e（要真实窗口/截图/视觉模型），只针对纯逻辑分支：
  - submit 按钮可见 → 立即停止
  - page_state == "finished" → 立即停止
  - confidence 低于阈值 → 暂停（返回 advance_step=False，不增加 step）
  - 答案未在 options 中 → 暂停
"""

from unittest.mock import MagicMock, patch

import pytest

from chaoxing_agent.core.state_machine import StateMachine, StepResult
from schemas.solver_schema import SolverResult
from schemas.vision_schema import VisionResult, VisionButton, VisionButtons, VisionConfidence, VisionOption


def _make_vision(page_state="question", question_type="single_choice",
                 options=None, submit_visible=False, next_visible=True,
                 text_conf=0.95, layout_conf=0.95):
    return VisionResult(
        page_state=page_state,
        question_type=question_type,
        question_text="题干",
        options=options or [VisionOption(key="A", text="选项A", box=[0, 100, 381, 150]),
                            VisionOption(key="B", text="选项B", box=[0, 200, 381, 250])],
        buttons=VisionButtons(
            previous=VisionButton(visible=False),
            next=VisionButton(visible=next_visible, text="下一题", box=[0, 800, 381, 850]),
            submit=VisionButton(visible=submit_visible, text="交卷" if submit_visible else ""),
        ),
        confidence=VisionConfidence(text=text_conf, layout=layout_conf),
    )


def _make_config():
    return {
        "target": {
            "selected_hwnd": 12345,
            "pid": 9999,
            "process_name": "test.exe",
            "client_rect": (0, 0, 388, 928),
        },
        "viewport": {
            "phone_viewport_in_client": {"x": 0, "y": 0, "width": 388, "height": 928},
            "phone_viewport_ratio": {"x": 0, "y": 0, "width": 1, "height": 1},
        },
        "timing": {
            "between_multi_select_clicks": 0.0,
            "before_click_next": 0.0,
            "after_click_next": 0.0,
            "extra_wait_if_page_not_changed": 0.0,
            "max_page_change_wait": 0.0,
        },
        "thresholds": {
            "vision_text_confidence": 0.75,
            "vision_layout_confidence": 0.75,
            "solver_confidence": 0.7,
            "page_change_pixel_ratio": 0.03,
            "window_size_change_ratio": 0.05,
        },
        "page_change": {
            "compare_region_ratio": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
            "compare_resize": [100, 100],
        },
        "runtime": {
            "max_steps": 10,
            "max_consecutive_errors": 3,
            "loading_retry_max": 1,
            "loading_retry_delay": 0.0,
            "pause_on_popup": True,
            "pause_on_unknown": True,
        },
    }


def _build_sm(config=None, model_services=None):
    cfg = config or _make_config()
    sm = StateMachine.__new__(StateMachine)  # 跳过 __init__（里面有真实 win32gui）
    sm.config = cfg
    sm.model_services = model_services or {"vision": {}, "solver": {}}
    sm.hwnd = cfg["target"]["selected_hwnd"]
    sm.expected_client_rect = tuple(cfg["target"]["client_rect"])
    sm.viewport = cfg["viewport"]
    sm.mapper = MagicMock()  # 全部 mock
    sm.vision_config = MagicMock()
    sm.solver_config = MagicMock()
    sm.trace_logger = MagicMock()
    sm.step = 0
    sm.consecutive_errors = 0
    sm.max_steps = cfg.get("runtime", {}).get("max_steps", 200)
    sm.max_consecutive_errors = cfg.get("runtime", {}).get("max_consecutive_errors", 3)
    sm.loading_retry_max = cfg.get("runtime", {}).get("loading_retry_max", 3)
    sm.loading_retry_delay = cfg.get("runtime", {}).get("loading_retry_delay", 1.0)
    sm.pause_on_popup = cfg.get("runtime", {}).get("pause_on_popup", True)
    sm.pause_on_unknown = cfg.get("runtime", {}).get("pause_on_unknown", True)
    sm.thresholds = cfg.get("thresholds", {})
    sm.timing = cfg.get("timing", {})
    return sm


def test_init_requires_hwnd():
    cfg = _make_config()
    cfg["target"]["selected_hwnd"] = None
    from chaoxing_agent.core.errors import FatalStopError
    with patch("chaoxing_agent.core.state_machine.CoordinateMapper", MagicMock()):
        with pytest.raises(FatalStopError, match="未绑定目标窗口"):
            StateMachine(cfg, {"vision": {}, "solver": {}})


def test_init_requires_viewport():
    cfg = _make_config()
    cfg["viewport"]["phone_viewport_in_client"]["width"] = 0
    from chaoxing_agent.core.errors import FatalStopError
    with patch("chaoxing_agent.core.state_machine.CoordinateMapper", MagicMock()):
        with pytest.raises(FatalStopError, match="未标定手机画面区域"):
            StateMachine(cfg, {"vision": {}, "solver": {}})


def test_submit_button_visible_triggers_immediate_stop():
    sm = _build_sm()
    fake_vision = _make_vision(submit_visible=True)
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=MagicMock(width=388, height=928)), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch("chaoxing_agent.core.state_machine.text_solve") as mock_solve:
        result = sm._process_one_step()
    assert result.should_stop is True
    assert result.stop_reason == "submit_detected"
    mock_solve.assert_not_called()  # 不能走到 text_solve


def test_page_state_finished_triggers_stop():
    sm = _build_sm()
    fake_vision = _make_vision(page_state="finished")
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=MagicMock(width=388, height=928)), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True):
        result = sm._process_one_step()
    assert result.should_stop is True
    assert result.stop_reason == "finished"


def test_low_vision_confidence_pauses_no_advance():
    sm = _build_sm()
    fake_vision = _make_vision(text_conf=0.3, layout_conf=0.95)  # text < 0.75
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=MagicMock(width=388, height=928)), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch.object(sm, "_pause_save", return_value=StepResult(advance_step=False)) as mock_pause:
        result = sm._process_one_step()
    assert result.advance_step is False
    mock_pause.assert_called_once()
    reason_arg = mock_pause.call_args[0][3]  # 第 4 个位置参数
    assert "视觉置信度过低" in reason_arg


def test_answer_not_in_options_pauses():
    sm = _build_sm()
    fake_vision = _make_vision()
    fake_solver = SolverResult(question_type="single_choice", answer=["X"], confidence=0.95, reason="")
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=MagicMock(width=388, height=928)), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch("chaoxing_agent.core.state_machine.text_solve", return_value=fake_solver), \
         patch.object(sm, "_pause_save", return_value=StepResult(advance_step=False)) as mock_pause:
        result = sm._process_one_step()
    assert result.advance_step is False
    reason = mock_pause.call_args[0][3]
    assert "无法映射" in reason


def test_window_gone_triggers_stop():
    sm = _build_sm()
    with patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=False):
        result = sm._process_one_step()
    assert result.should_stop is True
    assert result.stop_reason == "window_gone"


def test_no_next_button_pauses():
    sm = _build_sm()
    fake_vision = _make_vision(next_visible=False)
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=MagicMock(width=388, height=928)), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch.object(sm, "_pause_save", return_value=StepResult(advance_step=False)) as mock_pause:
        result = sm._process_one_step()
    assert result.advance_step is False
    reason = mock_pause.call_args[0][3]
    assert "未识别到下一题按钮" in reason


def test_next_button_box_out_of_screenshot_pauses_before_solving():
    """视觉模型返回的下一题 box 超出截图尺寸时，不应映射屏幕坐标并点击。"""
    sm = _build_sm()
    fake_vision = _make_vision(options=[
        VisionOption(key="A", text="选项A", box=[10, 100, 370, 150]),
        VisionOption(key="B", text="选项B", box=[10, 200, 370, 250]),
    ])
    fake_vision.buttons.next.box = [310, 900, 590, 960]  # 高度 770 的截图之外
    screenshot = MagicMock(width=380, height=770)
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=screenshot), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch("chaoxing_agent.core.state_machine.text_solve") as mock_solve, \
         patch.object(sm, "_pause_save", return_value=StepResult(advance_step=False)) as mock_pause:
        result = sm._process_one_step()

    assert result.advance_step is False
    mock_solve.assert_not_called()
    reason = mock_pause.call_args[0][3]
    assert "下一题按钮坐标越界" in reason


def test_option_box_out_of_screenshot_pauses_before_solving():
    """选项 box 超出截图尺寸时也不能继续求解和点击。"""
    sm = _build_sm()
    fake_vision = _make_vision(options=[VisionOption(key="A", text="选项A", box=[0, 100, 500, 150])])
    screenshot = MagicMock(width=388, height=928)
    with patch("chaoxing_agent.core.state_machine.vision_parse", return_value=fake_vision), \
         patch("chaoxing_agent.core.state_machine.capture_phone_screen", return_value=screenshot), \
         patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=True), \
         patch("chaoxing_agent.core.state_machine.text_solve") as mock_solve, \
         patch.object(sm, "_pause_save", return_value=StepResult(advance_step=False)) as mock_pause:
        result = sm._process_one_step()

    assert result.advance_step is False
    mock_solve.assert_not_called()
    reason = mock_pause.call_args[0][3]
    assert "选项 A 坐标越界" in reason


def test_window_size_changed_raises_fatal_stop():
    """窗口尺寸变化 > 阈值时，默认行为是 FatalStop（避免 pause 死循环）。"""
    from chaoxing_agent.core.errors import FatalStopError
    sm = _build_sm()
    with patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=False), \
         patch.object(sm, "_pause", return_value="retry") as mock_pause:
        with pytest.raises(FatalStopError, match="需要重新标定"):
            sm._process_one_step()
    # 提示了用户，但用户选了 retry → fatal
    mock_pause.assert_called_once()


def test_window_size_changed_skip_continues():
    """用户输入 skip 时可继续（advance=True）。"""
    sm = _build_sm()
    with patch("chaoxing_agent.core.state_machine.check_window_alive", return_value=True), \
         patch("chaoxing_agent.core.state_machine.check_window_size_unchanged", return_value=False), \
         patch.object(sm, "_pause", return_value="skip"):
        result = sm._process_one_step()
    assert result.advance_step is True
