"""状态机 — 主循环编排，串联全部流程"""

import time
from dataclasses import dataclass, field

from PIL import Image

from core.click_executor import click_next_button, click_options
from core.coordinate_mapper import CoordinateMapper
from core.errors import FatalStopError, PauseRequiredError, RecoverableError
from core.page_change_detector import wait_for_change
from core.screen_capture import capture_phone_screen, check_window_alive, check_window_size_unchanged
from core.trace_logger import TraceLogger
from models.model_config import get_solver_config, get_vision_config
from models.text_solver import solve as text_solve
from models.vision_parser import parse as vision_parse


@dataclass
class StepResult:
    should_stop: bool = False
    stop_reason: str = ""
    step_data: dict = field(default_factory=dict)
    advance_step: bool = False


class StateMachine:
    """主循环状态机。"""

    def __init__(self, config: dict, model_services: dict):
        self.config = config
        self.model_services = model_services

        target = config["target"]
        hwnd = target["selected_hwnd"]
        if not hwnd:
            raise FatalStopError("未绑定目标窗口，请先运行窗口选择。")

        self.hwnd = hwnd
        self.expected_client_rect = tuple(target.get("client_rect", (0, 0, 0, 0)))

        viewport = config["viewport"]
        if not viewport["phone_viewport_in_client"]["width"]:
            raise FatalStopError("未标定手机画面区域，请先运行区域选择。")

        self.viewport = viewport
        self.mapper = CoordinateMapper(self.hwnd, viewport)

        self.vision_config = get_vision_config(model_services)
        self.solver_config = get_solver_config(model_services)
        self.trace_logger = TraceLogger()

        self.step = 0
        self.consecutive_errors = 0

        runtime = config.get("runtime", {})
        self.max_steps = runtime.get("max_steps", 200)
        self.max_consecutive_errors = runtime.get("max_consecutive_errors", 3)
        self.loading_retry_max = runtime.get("loading_retry_max", 3)
        self.loading_retry_delay = runtime.get("loading_retry_delay", 1.0)
        self.pause_on_popup = runtime.get("pause_on_popup", True)
        self.pause_on_unknown = runtime.get("pause_on_unknown", True)

        self.thresholds = config.get("thresholds", {})
        self.timing = config.get("timing", {})

    def run(self):
        """主循环入口。"""
        print(f"\n{'=' * 50}")
        print("ChaoxingAgent v1 — 开始自动循环")
        print(f"最大步骤数: {self.max_steps}")
        print(f"{'=' * 50}\n")

        try:
            while self.step < self.max_steps:
                self.mapper.refresh()

                try:
                    result = self._process_one_step()
                except RecoverableError as e:
                    self.consecutive_errors += 1
                    print(f"[WARN] 可恢复异常 (第{self.consecutive_errors}次): {e}")
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        raise FatalStopError(f"连续异常超过 {self.max_consecutive_errors} 次") from e
                    time.sleep(1)
                    continue
                except PauseRequiredError as e:
                    self._pause(str(e))
                    continue

                if result.should_stop:
                    self._handle_stop(result)
                    return

                if result.advance_step:
                    self.step += 1
                    self.consecutive_errors = 0

        except FatalStopError as e:
            print(f"\n[FATAL] {e}")
            self.trace_logger.save_stop(str(e))
        except KeyboardInterrupt:
            print("\n[INFO] 用户中断")
            self.trace_logger.save_stop("用户中断 (Ctrl+C)")

        print(f"\n处理完成。共处理 {self.step} 题。")
        if self.step >= self.max_steps:
            self.trace_logger.save_stop("max_steps")
        print(f"Trace 目录: {self.trace_logger.session_dir}")

    def _process_one_step(self) -> StepResult:
        """处理一道题的完整流程。"""
        print(f"\n--- Step {self.step + 1} ---")

        if not check_window_alive(self.hwnd):
            return StepResult(should_stop=True, stop_reason="window_gone")

        if not check_window_size_unchanged(
            self.hwnd,
            self.expected_client_rect,
            self.thresholds.get("window_size_change_ratio", 0.05),
        ):
            pause_result = self._pause("窗口尺寸已变化，请重新标定手机画面区域")
            return StepResult(advance_step=pause_result == "skip")

        screenshot = capture_phone_screen(self.hwnd, self.viewport)
        print(f"  截图: {screenshot.width}x{screenshot.height}")

        vision = vision_parse(screenshot, self.vision_config)
        print(
            f"  page_state={vision.page_state} type={vision.question_type} "
            f"confidence(text={vision.confidence.text:.2f} layout={vision.confidence.layout:.2f})"
        )

        # Hard safety boundary: submit detection always stops immediately.
        if vision.page_state == "submit" or vision.buttons.submit.visible:
            return StepResult(should_stop=True, stop_reason="submit_detected")

        if vision.page_state == "finished":
            return StepResult(should_stop=True, stop_reason="finished")

        if vision.popup.visible and self.pause_on_popup:
            return self._pause_save(screenshot, vision, None, "检测到弹窗，请手动处理后按 Enter 继续")

        if vision.page_state == "unknown" and self.pause_on_unknown:
            return self._pause_save(screenshot, vision, None, "无法识别页面状态，请检查后按 Enter 继续")

        if vision.page_state == "loading":
            return self._handle_loading(screenshot)

        if vision.page_state != "question":
            return self._pause_save(screenshot, vision, None, f"未预期的页面状态: {vision.page_state}，请检查后按 Enter 继续")

        vt = self.thresholds.get("vision_text_confidence", 0.75)
        vl = self.thresholds.get("vision_layout_confidence", 0.75)
        if vision.confidence.text < vt or vision.confidence.layout < vl:
            return self._pause_save(
                screenshot,
                vision,
                None,
                f"视觉置信度过低 (text={vision.confidence.text:.2f} layout={vision.confidence.layout:.2f})",
            )

        if not vision.options:
            return self._pause_save(screenshot, vision, None, "视觉模型未识别到选项")

        if not vision.buttons.next.visible or not vision.buttons.next.box:
            return self._pause_save(screenshot, vision, None, "未识别到下一题按钮")

        opts_dict = {opt.key: opt.text for opt in vision.options}
        print(f"  题干: {vision.question_text[:80]}...")
        print(f"  选项: {opts_dict}")

        solver = text_solve(vision.question_type, vision.question_text, opts_dict, self.solver_config)
        print(f"  答案: {solver.answer} confidence={solver.confidence:.2f}")

        if solver.confidence < self.thresholds.get("solver_confidence", 0.70):
            return self._pause_save(screenshot, vision, solver, f"文本模型置信度过低 ({solver.confidence:.2f})")

        for answer in solver.answer:
            if answer not in opts_dict:
                return self._pause_save(screenshot, vision, solver, f"答案 '{answer}' 无法映射到选项 {list(opts_dict.keys())}")

        click_options(solver.answer, vision.options, self.mapper, self.timing)

        clicked = []
        for answer_key in solver.answer:
            opt = next(o for o in vision.options if o.key == answer_key)
            scx, scy = self.mapper.box_center_screen(opt.box)
            clicked.append(
                {
                    "key": answer_key,
                    "box": opt.box,
                    "image_center": [(opt.box[0] + opt.box[2]) // 2, (opt.box[1] + opt.box[3]) // 2],
                    "screen_center": [scx, scy],
                }
            )

        before_img = capture_phone_screen(self.hwnd, self.viewport)
        click_next_button(vision.buttons.next.box, self.mapper, self.timing)

        def _capture():
            return capture_phone_screen(self.hwnd, self.viewport)

        changed, after_img = wait_for_change(before_img, _capture, self.config)
        if not changed:
            return self._pause_save(
                after_img or before_img,
                vision,
                solver,
                f"点击下一题后页面未变化（已等待{self.timing.get('max_page_change_wait', 3.0)}秒）",
            )

        nscx, nscy = self.mapper.box_center_screen(vision.buttons.next.box)
        step_data = {
            "step": self.step + 1,
            "screenshot_img": screenshot,
            "page_state": vision.page_state,
            "question_type": vision.question_type,
            "question": vision.question_text,
            "options": opts_dict,
            "vision_confidence": {"text": vision.confidence.text, "layout": vision.confidence.layout},
            "vision_raw_json": vision.model_dump(),
            "solver_answer": solver.answer,
            "solver_confidence": solver.confidence,
            "solver_reason": solver.reason,
            "solver_raw_json": solver.model_dump(),
            "clicked_options": clicked,
            "next_button": {
                "box": vision.buttons.next.box,
                "image_center": [
                    (vision.buttons.next.box[0] + vision.buttons.next.box[2]) // 2,
                    (vision.buttons.next.box[1] + vision.buttons.next.box[3]) // 2,
                ],
                "screen_center": [nscx, nscy],
            },
            "page_changed": True,
            "error": None,
        }
        self.trace_logger.save_step(step_data)
        return StepResult(step_data=step_data, advance_step=True)

    def _handle_loading(self, screenshot: Image.Image) -> StepResult:
        """处理 loading 状态。"""
        for i in range(self.loading_retry_max):
            print(f"  页面 loading，等待 {self.loading_retry_delay}s 后重试 ({i + 1}/{self.loading_retry_max})")
            time.sleep(self.loading_retry_delay)
            screenshot = capture_phone_screen(self.hwnd, self.viewport)
            vision = vision_parse(screenshot, self.vision_config)
            if vision.page_state != "loading":
                print(f"  页面状态变为: {vision.page_state}")
                return StepResult()
        return self._pause_save(screenshot, None, None, "页面持续 loading，请检查")

    def _handle_stop(self, result: StepResult):
        """处理停止。"""
        reason = result.stop_reason
        print(f"\n[STOP] 停止原因: {reason}")
        if reason == "submit_detected":
            print("[INFO] 检测到交卷按钮，已停止自动操作。请手动接管。")
        self.trace_logger.save_stop(reason)
        try:
            img = capture_phone_screen(self.hwnd, self.viewport)
            img.save(self.trace_logger.session_dir / "FINAL_SCREENSHOT.png")
        except Exception:
            pass

    def _pause(self, reason: str) -> str:
        """暂停并等待用户指令。"""
        print(f"\n[PAUSE] {reason}")
        print("  按 Enter 重试当前步骤 / 输入 'skip' 跳过 / 输入 'quit' 退出")
        choice = input("  > ").strip().lower()
        if choice == "quit":
            raise FatalStopError(f"用户选择退出: {reason}")
        if choice == "skip":
            return "skip"
        return "retry"

    def _pause_save(self, screenshot, vision_result, solver_result, reason: str) -> StepResult:
        """暂停并保存现场。"""
        self.trace_logger.save_pause(
            self.step + 1,
            screenshot,
            vision_result.model_dump() if vision_result else {},
            solver_result.model_dump() if solver_result else None,
            reason,
        )
        pause_result = self._pause(reason)
        return StepResult(advance_step=pause_result == "skip")
