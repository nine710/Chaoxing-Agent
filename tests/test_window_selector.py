"""window_selector 的回归测试。"""

import pytest

from chaoxing_agent.core import window_selector as ws


def test_find_processes_by_name_matches_with_or_without_exe(monkeypatch):
    """裸名 'vivoScreen' 应能匹配 'vivoScreen.exe' 进程。"""
    from unittest.mock import MagicMock

    fake_proc = MagicMock()
    fake_proc.info = {"pid": 123, "name": "vivoScreen.exe"}
    monkeypatch.setattr(ws.psutil, "process_iter", lambda attrs: iter([fake_proc]))

    found = ws.find_processes_by_name("vivoScreen")
    assert len(found) == 1
    assert found[0] is fake_proc


def test_find_processes_by_name_case_insensitive(monkeypatch):
    """大小写不敏感。"""
    from unittest.mock import MagicMock
    fake_proc = MagicMock()
    fake_proc.info = {"pid": 1, "name": "VIVOSCREEN.EXE"}
    monkeypatch.setattr(ws.psutil, "process_iter", lambda attrs: iter([fake_proc]))
    found = ws.find_processes_by_name("vivoscreen")
    assert len(found) == 1


def test_find_process_by_pid_returns_none_for_missing(monkeypatch):
    import psutil
    monkeypatch.setattr(psutil, "Process", lambda pid: (_ for _ in ()).throw(psutil.NoSuchProcess(pid)))
    assert ws.find_process_by_pid(99999) is None


def test_enumerate_visible_windows_filters_by_pid(monkeypatch):
    """只返回匹配 PID 的可见窗口。"""
    from unittest.mock import MagicMock

    visible_hwnds = [100, 200, 300]
    monkeypatch.setattr(ws.win32gui, "EnumWindows",
                        lambda cb, ctx: [cb(h, ctx) for h in visible_hwnds] and True)
    monkeypatch.setattr(ws.win32gui, "IsWindowVisible", lambda h: True)
    monkeypatch.setattr(ws.win32gui, "IsIconic", lambda h: False)
    # 100/200 属于 pid=42，300 属于 pid=99
    def fake_get_tid(h):
        return (0, 42) if h in (100, 200) else (0, 99)
    monkeypatch.setattr(ws.win32process, "GetWindowThreadProcessId", fake_get_tid)

    fake_proc = MagicMock()
    fake_proc.name.return_value = "test.exe"
    monkeypatch.setattr(ws.psutil, "Process", lambda pid: fake_proc)

    # 关键：内部 _get_window_info 也得 mock（避免真实 win32gui.GetWindowText）
    monkeypatch.setattr(ws, "_get_window_info",
                        lambda hwnd, pid, name: ws.WindowInfo(
                            hwnd=hwnd, pid=pid, process_name=name, window_title=f"t{hwnd}",
                            client_rect=(0, 0, 100, 100), screen_rect=(0, 0, 100, 100),
                            width=100, height=100,
                        ))

    out = ws.enumerate_visible_windows(42)
    assert len(out) == 2
    assert {w.hwnd for w in out} == {100, 200}


def test_select_process_raises_systemexit_when_no_match(monkeypatch):
    monkeypatch.setattr(ws, "find_processes_by_name", lambda name: [])
    with pytest.raises(SystemExit, match="未找到匹配"):
        ws.select_process("nonexistent")


def test_select_process_returns_single_match(monkeypatch):
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.pid = 42
    fake.name.return_value = "test.exe"
    monkeypatch.setattr(ws, "find_processes_by_name", lambda name: [fake])
    result = ws.select_process("test")
    assert result is fake


def test_select_process_prompts_when_multiple(monkeypatch, capsys):
    from unittest.mock import MagicMock
    p1 = MagicMock(); p1.pid = 1; p1.name.return_value = "test1.exe"
    p2 = MagicMock(); p2.pid = 2; p2.name.return_value = "test2.exe"
    monkeypatch.setattr(ws, "find_processes_by_name", lambda name: [p1, p2])
    monkeypatch.setattr(ws, "psutil", ws.psutil)  # ensure import is intact
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = ws.select_process("test")
    assert result is p2
