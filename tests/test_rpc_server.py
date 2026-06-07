"""RPC server 协议层测试 — 用内存流模拟 stdin/stdout。"""
import asyncio
import json
import pytest
from io import StringIO

from chaoxing_agent.rpc_server import RpcServer


class FakeStdin:
    """读 stdin 的最小 mock（同步 readline，配合 run_in_executor）。"""
    def __init__(self, lines: list[str]):
        self.lines = list(lines)
        self.pos = 0

    def readline(self) -> str:
        if self.pos >= len(self.lines):
            return ""
        line = self.lines[self.pos]
        self.pos += 1
        return line + "\n"


class FakeStdout:
    def __init__(self):
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        self.lines.append(line)


@pytest.mark.asyncio
async def test_dispatches_request_and_writes_response():
    stdin = FakeStdin([
        json.dumps({"type": "request", "id": 1, "method": "ping", "params": {}}),
    ])
    stdout = FakeStdout()
    server = RpcServer(stdin=stdin, stdout=stdout)

    async def handle_ping(params: dict) -> dict:
        return {"pong": True}

    server.register("ping", handle_ping)

    task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.1)  # 让 server 处理
    task.cancel()

    assert len(stdout.lines) == 1
    resp = json.loads(stdout.lines[0])
    assert resp["type"] == "response"
    assert resp["id"] == 1
    assert resp["result"] == {"pong": True}


@pytest.mark.asyncio
async def test_writes_error_on_unknown_method():
    stdin = FakeStdin([
        json.dumps({"type": "request", "id": 2, "method": "nope", "params": {}}),
    ])
    stdout = FakeStdout()
    server = RpcServer(stdin=stdin, stdout=stdout)

    task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.1)
    task.cancel()

    resp = json.loads(stdout.lines[0])
    assert resp["type"] == "error"
    assert resp["id"] == 2
    assert resp["error"]["code"] == "unknown_method"


@pytest.mark.asyncio
async def test_emits_event_to_stdout():
    stdin = FakeStdin([])
    stdout = FakeStdout()
    server = RpcServer(stdin=stdin, stdout=stdout)

    await server.emit("ready", {"version": "0.2.0"})
    await asyncio.sleep(0.01)

    msg = json.loads(stdout.lines[0])
    assert msg["type"] == "event"
    assert msg["event"] == "ready"
    assert msg["data"] == {"version": "0.2.0"}