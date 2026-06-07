"""PauseGate — 异步同步原语，替换 StateMachine 中的 input() 阻塞。

用法：
    gate = PauseGate()
    # 状态机侧：
    decision = await gate.wait(step, reason)
    # RPC handler 侧（前端发 pause_decision 时调用）：
    gate.resolve(decision)

内部使用 asyncio.Queue 确保串行化：每个 resolve() 只唤醒一个 waiter。
"""
import asyncio
from typing import Optional


class PauseGate:
    def __init__(self):
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._pending = False

    async def wait(self, step: int, reason: str) -> str:
        """状态机调用：阻塞等待前端发决策。"""
        self._pending = True
        decision = await self._queue.get()
        self._pending = False
        return decision

    def resolve(self, decision: str) -> None:
        """RPC handler 调用：解除阻塞。"""
        self._queue.put_nowait(decision)

    def is_pending(self) -> bool:
        """前端用：当前是否在等决策。"""
        return self._pending