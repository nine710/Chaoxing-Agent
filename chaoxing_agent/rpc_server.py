"""JSON-RPC server — 读 stdin NDJSON 请求，分发到 handler，stdout 推响应/事件。

设计：
- 一个 asyncio 任务从 stdin 持续读行
- 每行 parse 成 dict，分发到注册的 handler（async 或 sync 都支持）
- handler 返回值作为 response.result
- handler 抛异常 → response.error（code="internal_error"）
- 未知 method → error(code="unknown_method")
- emit() 是 fire-and-forget 推事件到 stdout
- stdout writer 用 asyncio.Lock 序列化（避免多协程交错写）
"""
import asyncio
import inspect
import json
import logging
import sys
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger(__name__)


HandlerFn = Callable[[dict], "Awaitable[dict] | dict"]


class RpcServer:
    def __init__(self, stdin=None, stdout=None):
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stdout = stdout if stdout is not None else sys.stdout
        self._handlers: dict[str, HandlerFn] = {}
        self._write_lock = asyncio.Lock()

    def register(self, method: str, handler: HandlerFn) -> None:
        self._handlers[method] = handler

    async def serve(self) -> None:
        """主循环：读 stdin 一行行分发。"""
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, self._stdin.readline)
            if not line:
                return  # stdin EOF
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception as e:
                log.warning(f"parse error: {e}")
                continue
            if msg.get("type") != "request":
                continue
            asyncio.create_task(self._dispatch(msg))

    async def _dispatch(self, msg: dict) -> None:
        method = msg.get("method", "")
        req_id = msg.get("id", 0)
        params = msg.get("params", {})
        handler = self._handlers.get(method)
        if handler is None:
            await self._write_error(req_id, "unknown_method", f"unknown method: {method}")
            return
        try:
            result = handler(params)
            if inspect.isawaitable(result):
                result = await result
            await self._write_response(req_id, result)
        except Exception as e:
            log.exception(f"handler {method} failed")
            await self._write_error(req_id, "internal_error", str(e))

    async def emit(self, event: str, data: dict) -> None:
        """推事件到 stdout。"""
        msg = json.dumps({"type": "event", "event": event, "data": data}, ensure_ascii=False, default=str)
        async with self._write_lock:
            self._stdout.write_line(msg + "\n")

    async def _write_response(self, req_id: int, result: Any) -> None:
        msg = json.dumps({"type": "response", "id": req_id, "result": result}, ensure_ascii=False, default=str)
        async with self._write_lock:
            self._stdout.write_line(msg + "\n")

    async def _write_error(self, req_id: int, code: str, message: str, detail: Optional[dict] = None) -> None:
        err = {"code": code, "message": message, "detail": detail or {}}
        msg = json.dumps({"type": "error", "id": req_id, "error": err}, ensure_ascii=False)
        async with self._write_lock:
            self._stdout.write_line(msg + "\n")