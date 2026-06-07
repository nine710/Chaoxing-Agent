"""PauseGate 异步同步原语测试。"""
import asyncio
import pytest

from chaoxing_agent.pause_gate import PauseGate


@pytest.mark.asyncio
async def test_wait_blocks_until_resolve():
    gate = PauseGate()
    result = asyncio.create_task(gate.wait(1, "test"))
    await asyncio.sleep(0.05)
    assert not result.done()
    gate.resolve("skip")
    decision = await asyncio.wait_for(result, timeout=1.0)
    assert decision == "skip"


@pytest.mark.asyncio
async def test_resolve_resets_state():
    gate = PauseGate()
    task1 = asyncio.create_task(gate.wait(1, "first"))
    gate.resolve("retry")
    await task1

    # 第二次调用
    task2 = asyncio.create_task(gate.wait(2, "second"))
    gate.resolve("quit")
    decision = await asyncio.wait_for(task2, timeout=1.0)
    assert decision == "quit"


@pytest.mark.asyncio
async def test_concurrent_waiters_serialize():
    """多次 wait 应串行 — 第一个 resolve 后才能 wait 第二次。"""
    gate = PauseGate()
    task1 = asyncio.create_task(gate.wait(1, "a"))
    await asyncio.sleep(0.01)
    gate.resolve("retry")
    await task1

    # 第二个 waiter 立即 resolve 之前，第三个不应触发
    task2 = asyncio.create_task(gate.wait(2, "b"))
    task3 = asyncio.create_task(gate.wait(3, "c"))
    await asyncio.sleep(0.01)
    assert not task2.done()
    assert not task3.done()
    gate.resolve("skip")
    d2 = await asyncio.wait_for(task2, timeout=1.0)
    # task3 还在等
    assert not task3.done()
    gate.resolve("quit")
    d3 = await asyncio.wait_for(task3, timeout=1.0)
    assert d2 == "skip"
    assert d3 == "quit"