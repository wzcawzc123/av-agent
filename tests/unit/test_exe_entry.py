"""桌面入口纯逻辑单元测试（不依赖 PySide6 图形环境）。"""

from unittest.mock import MagicMock

from desktop.main import pick_free_port, wait_until_ready


def test_pick_free_port_returns_given_when_free(monkeypatch):
    monkeypatch.setattr("desktop.main._port_is_free", lambda port: True)
    assert pick_free_port(8000) == 8000


def test_pick_free_port_scans_upward(monkeypatch):
    taken = {8000, 8001}
    monkeypatch.setattr("desktop.main._port_is_free", lambda port: port not in taken)
    assert pick_free_port(8000) == 8002


def test_wait_until_ready_returns_true_on_200(monkeypatch):
    resp = MagicMock(status_code=200)
    get = MagicMock(return_value=resp)
    monkeypatch.setattr("httpx.get", get)
    assert wait_until_ready("http://127.0.0.1:8000", timeout=1) is True
    get.assert_called()


def test_wait_until_ready_returns_false_on_failure(monkeypatch):
    def flaky(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr("httpx.get", flaky)
    assert wait_until_ready("http://127.0.0.1:8000", timeout=0.5) is False
