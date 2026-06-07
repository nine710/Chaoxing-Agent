"""AsyncStateMachine 单元测试 — 用 mock 替换业务逻辑，只测状态机骨架。

这些测试不依赖实际的截图、模型、窗口环境。
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chaoxing_agent.async_state_machine import AsyncStateMachine
from chaoxing_agent.config_holder import ConfigHolder
from chaoxing_agent.core.errors import FatalStopError
from chaoxing_agent.pause_gate import PauseGate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config(tmp_path: Path) -> ConfigHolder:
    return ConfigHolder(
        {
            "target": {
                "selected_hwnd": 12345,
                "process_name": "test.exe",
                "pid": 100,
                "window_title": "测试",
                "client_rect": [0, 0, 1280, 720],
            },
            "viewport": {
                "phone_viewport_in_client": {"x": 100, "y": 50, "width": 720, "height": 1280},
            },
            "runtime": {"max_steps": 3},
            "thresholds": {},
            "timing": {},
            "page_change": {},
        },
        config_path=tmp_path / "config.json",
    )


@pytest.fixture
def ctx(tmp_path, config):
    rpc = MagicMock()
    rpc.emit = AsyncMock()
    pause_gate = PauseGate()
    state = {}
    return type("Ctx", (), {
        "config": config,
        "rpc": rpc,
        "pause_gate": pause_gate,
        "state": state,
    })()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionId:
    def test_session_id_format(self, ctx):
        """session_id 应为 'YYYY-MM-DD_HH-MM-SS' 格式。"""
        sm = AsyncStateMachine(ctx, {})
        assert len(sm.session_id) == 19, f"got {sm.session_id!r}"
        assert "_" in sm.session_id
        # 验证格式: YYYY-MM-DD_HH-MM-SS
        parts = sm.session_id.split("_")
        assert len(parts) == 2
        assert len(parts[0].split("-")) == 3  # YYYY-MM-DD
        assert len(parts[1].split("-")) == 3  # HH-MM-SS


class TestRequestStop:
    def test_request_stop_sets_flag(self, ctx):
        """request_stop() 应设置 _stop_requested = True。"""
        sm = AsyncStateMachine(ctx, {})
        assert sm._stop_requested is False
        sm.request_stop()
        assert sm._stop_requested is True

    def test_request_stop_called_multiple_times(self, ctx):
        """多次调用 request_stop() 应保持 True。"""
        sm = AsyncStateMachine(ctx, {})
        sm.request_stop()
        sm.request_stop()
        assert sm._stop_requested is True


class TestStepCounter:
    def test_step_starts_at_zero(self, ctx):
        """step 初始值为 0。"""
        sm = AsyncStateMachine(ctx, {})
        assert sm.step == 0

    def test_step_increment(self, ctx):
        """模拟跑 1 步后 step == 1。"""
        sm = AsyncStateMachine(ctx, {})
        sm.step += 1
        assert sm.step == 1


class TestEventEmission:
    @pytest.mark.asyncio
    async def test_emit_log_calls_rpc(self, ctx):
        """_emit_log 应调用 rpc.emit("log", ...)。"""
        sm = AsyncStateMachine(ctx, {})
        await sm._emit_log("INFO", "测试消息")
        # 至少有一次 emit("log", ...) 调用
        assert any(
            call.args[0] == "log"
            for call in ctx.rpc.emit.call_args_list
        ), "rpc.emit was not called with 'log'"

    @pytest.mark.asyncio
    async def test_emit_event_calls_rpc(self, ctx):
        """_emit_event 应调用 rpc.emit 并透传 event 名称和数据。"""
        sm = AsyncStateMachine(ctx, {})
        await sm._emit_event("test_event", {"k": 1})
        ctx.rpc.emit.assert_called_once_with("test_event", {"k": 1})

    @pytest.mark.asyncio
    async def test_emit_log_with_extra_logger(self, ctx):
        """_emit_log 应同时写 Python logger。"""
        sm = AsyncStateMachine(ctx, {})
        with patch("chaoxing_agent.async_state_machine.log") as mock_log:
            await sm._emit_log("WARN", "测试警告")
            mock_log.warn.assert_called_once()
            # emit 到 rpc 也应发生
            assert any(
                call.args[0] == "log"
                for call in ctx.rpc.emit.call_args_list
            )

    @pytest.mark.asyncio
    async def test_emit_event_handles_rpc_none(self, ctx):
        """rpc 为 None 时 _emit_event 不应抛异常。"""
        ctx_no_rpc = type("Ctx", (), {
            "config": ctx.config,
            "rpc": None,
            "pause_gate": ctx.pause_gate,
            "state": ctx.state,
        })()
        sm = AsyncStateMachine(ctx_no_rpc, {})
        # 不应抛异常
        await sm._emit_event("test_event", {"k": 1})
        # 也不应涉及 emit
        assert True  # 没抛就通过


class TestPauseIntegration:
    """验证暂停流程的基本协调（不涉及 _pause_save 里的 TraceLogger / capture）。"""

    @pytest.mark.asyncio
    async def test_pause_gate_decision(self, ctx):
        """_pause 应 emit paused 事件，等待 gate.resolve(), 返回 decision。"""
        sm = AsyncStateMachine(ctx, {})
        sm._hwnd = 12345
        sm._viewport = {"phone_viewport_in_client": {"x": 0, "y": 0, "width": 100, "height": 100}}

        with patch("chaoxing_agent.async_state_machine.capture_phone_screen") as mock_cap:
            # 模拟截图返回一个小 PIL Image
            from PIL import Image
            mock_img = Image.new("RGB", (100, 100), (255, 0, 0))
            mock_cap.return_value = mock_img

            # 异步发送决策
            async def resolve_after_delay():
                await asyncio.sleep(0.05)
                ctx.pause_gate.resolve("skip")

            pause_task = asyncio.create_task(sm._pause("测试暂停"))
            resolve_task = asyncio.create_task(resolve_after_delay())
            decision = await asyncio.wait_for(pause_task, timeout=2.0)
            await resolve_task

            assert decision == "skip"
            # 验证 paused 事件已 emit
            assert any(
                call.args[0] == "paused"
                for call in ctx.rpc.emit.call_args_list
            )


class TestRunInitialization:
    """test run() 的初始化逻辑，但不实际运行主循环。"""

    @pytest.mark.asyncio
    async def test_ensure_ready_raises_without_hwnd(self, ctx):
        """_ensure_ready 在无 selected_hwnd 时应抛 FatalStopError。"""
        ctx.config._data["target"]["selected_hwnd"] = None
        sm = AsyncStateMachine(ctx, {})
        with pytest.raises(FatalStopError, match="未绑定目标窗口"):
            sm._ensure_ready()

    @pytest.mark.asyncio
    async def test_ensure_ready_raises_without_viewport(self, ctx):
        """_ensure_ready 在无 viewport 时应抛 FatalStopError。"""
        ctx.config._data["viewport"]["phone_viewport_in_client"]["width"] = 0
        sm = AsyncStateMachine(ctx, {})
        with pytest.raises(FatalStopError, match="未标定手机画面区域"):
            sm._ensure_ready()


class TestImgToB64:
    def test_img_to_b64_returns_string(self, ctx):
        """_img_to_b64 应返回 base64 ASCII 字符串。"""
        from PIL import Image
        sm = AsyncStateMachine(ctx, {})
        img = Image.new("RGB", (10, 10), (0, 128, 255))
        b64 = sm._img_to_b64(img)
        assert isinstance(b64, str)
        assert len(b64) > 0
        # 验证是合法 base64
        import base64
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0


class TestRunLoopStructure:
    """测试 run() 的循环结构：max_steps、stop_requested、CancelledError。"""

    @pytest.mark.asyncio
    async def test_run_with_max_steps(self, ctx):
        """当 max_steps=0，run 应立即退出，不抛异常。"""
        ctx.config._data["runtime"]["max_steps"] = 0
        sm = AsyncStateMachine(ctx, {})
        with (
            patch("chaoxing_agent.async_state_machine.load_model_services") as mock_load,
            patch("chaoxing_agent.async_state_machine.get_vision_config"),
            patch("chaoxing_agent.async_state_machine.get_solver_config"),
            patch("chaoxing_agent.async_state_machine.TraceLogger"),
            patch("chaoxing_agent.async_state_machine.CoordinateMapper"),
        ):
            mock_load.return_value = {"vision": {}, "solver": {}}
            await sm.run()
            # 不应报错，且 stopped 事件应 emit
            assert any(
                call.args[0] == "stopped"
                for call in ctx.rpc.emit.call_args_list
            ), "stopped event should be emitted"

    @pytest.mark.asyncio
    async def test_run_stop_requested_before_start(self, ctx):
        """request_stop() 后再 run 应直接退出。"""
        ctx.config._data["runtime"]["max_steps"] = 100
        sm = AsyncStateMachine(ctx, {})
        sm.request_stop()
        with (
            patch("chaoxing_agent.async_state_machine.load_model_services") as mock_load,
            patch("chaoxing_agent.async_state_machine.get_vision_config"),
            patch("chaoxing_agent.async_state_machine.get_solver_config"),
            patch("chaoxing_agent.async_state_machine.TraceLogger"),
            patch("chaoxing_agent.async_state_machine.CoordinateMapper"),
        ):
            mock_load.return_value = {"vision": {}, "solver": {}}
            await sm.run()
            assert sm.step == 0, "should not process any step"

    @pytest.mark.asyncio
    async def test_run_cancelled_cleanly(self, ctx):
        """CancelledError 应透传，不吞没。"""
        ctx.config._data["runtime"]["max_steps"] = 200
        sm = AsyncStateMachine(ctx, {})

        # 用 patch 让 run() 在主循环里被取消
        original_emit_event = sm._emit_event

        async def cancel_emit(event, data):
            if event == "step_started":
                raise asyncio.CancelledError()
            await original_emit_event(event, data)

        with (
            patch("chaoxing_agent.async_state_machine.load_model_services") as mock_load,
            patch("chaoxing_agent.async_state_machine.get_vision_config"),
            patch("chaoxing_agent.async_state_machine.get_solver_config"),
            patch("chaoxing_agent.async_state_machine.TraceLogger"),
            patch("chaoxing_agent.async_state_machine.CoordinateMapper"),
        ):
            mock_load.return_value = {"vision": {}, "solver": {}}
            with patch.object(sm, "_emit_event", side_effect=cancel_emit):
                task = asyncio.create_task(sm.run())
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=2.0)


class TestHandlerContextIntegration:
    """验证 AsyncStateMachine 与 rpc_handlers.HandlerContext 的兼容性。

    Phase 5 中 _start_run handler 做了:
      from chaoxing_agent.async_state_machine import AsyncStateMachine
      sm = AsyncStateMachine(ctx, params)
      ctx.state["sm"] = sm
    """

    def test_constructor_matches_handler_context_signature(self, ctx):
        """AsyncStateMachine 应能用 rpc_handlers.HandlerContext 实例化。"""
        sm = AsyncStateMachine(ctx, {})
        assert isinstance(sm, AsyncStateMachine)

    def test_state_dict_compatible(self, ctx):
        """ctx.state 能存放 sm 且类型正确。"""
        sm = AsyncStateMachine(ctx, {})
        ctx.state["sm"] = sm
        assert ctx.state["sm"] is sm

    def test_request_stop_from_state(self, ctx):
        """通过 ctx.state["sm"].request_stop() 能触发停止。"""
        sm = AsyncStateMachine(ctx, {})
        ctx.state["sm"] = sm
        ctx.state["sm"].request_stop()
        assert sm._stop_requested is True

    def test_run_returns_coroutine(self, ctx):
        """run() 应返回一个 coroutine（而非同步执行）。"""
        sm = AsyncStateMachine(ctx, {})
        coro = sm.run()
        import inspect
        assert inspect.iscoroutine(coro), "run() should return a coroutine"
        # 关闭 coroutine 避免 RuntimeWarning
        coro.close()