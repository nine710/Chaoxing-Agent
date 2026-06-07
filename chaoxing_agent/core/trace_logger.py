"""Trace 日志 — 每步截图 + JSON 落盘"""

import json
from datetime import datetime
from pathlib import Path


class TraceLogger:
    """管理 trace/ 目录，保存每步截图和 JSON"""

    def __init__(self, base_dir: str = "trace"):
        self.base_dir = Path(base_dir)
        session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = self.base_dir / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Trace] 日志目录: {self.session_dir}")

    def save_step(self, step_data: dict):
        """保存一步的截图和 JSON"""
        step_num = step_data["step"]
        timestamp = datetime.now().isoformat()

        screenshot_filename = f"step_{step_num:03d}.png"
        screenshot_path = self.session_dir / screenshot_filename
        img = step_data.pop("screenshot_img", None)
        if img:
            img.save(screenshot_path)

        trace_entry = {
            "step": step_num,
            "timestamp": timestamp,
            "screenshot": str(screenshot_path),
            "page_state": step_data.get("page_state"),
            "question_type": step_data.get("question_type"),
            "question": step_data.get("question", ""),
            "options": step_data.get("options"),
            "vision_confidence": step_data.get("vision_confidence"),
            "vision_raw_json": step_data.get("vision_raw_json"),
            "solver_answer": step_data.get("solver_answer"),
            "solver_confidence": step_data.get("solver_confidence"),
            "solver_reason": step_data.get("solver_reason", ""),
            "solver_raw_json": step_data.get("solver_raw_json"),
            "clicked_options": step_data.get("clicked_options", []),
            "next_button": step_data.get("next_button"),
            "page_changed": step_data.get("page_changed"),
            "page_change_ratio": step_data.get("page_change_ratio"),
            "error": step_data.get("error"),
        }

        json_filename = f"step_{step_num:03d}.json"
        json_path = self.session_dir / json_filename
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(trace_entry, f, ensure_ascii=False, indent=2)

    def save_pause(self, step_num: int, screenshot, vision_result: dict, solver_result: dict | None, reason: str):
        """暂停时额外保存现场"""
        pause_dir = self.session_dir / f"pause_step_{step_num:03d}"
        pause_dir.mkdir(exist_ok=True)

        if screenshot:
            screenshot.save(pause_dir / "screenshot_at_pause.png")

        with open(pause_dir / "vision_result.json", "w", encoding="utf-8") as f:
            json.dump(vision_result, f, ensure_ascii=False, indent=2)

        if solver_result:
            with open(pause_dir / "solver_result.json", "w", encoding="utf-8") as f:
                json.dump(solver_result, f, ensure_ascii=False, indent=2)

        (pause_dir / "pause_reason.txt").write_text(reason, encoding="utf-8")

    def save_stop(self, reason: str):
        """最终停止时记录原因"""
        (self.session_dir / "STOP_REASON.txt").write_text(reason, encoding="utf-8")
