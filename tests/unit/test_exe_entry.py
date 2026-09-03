"""exe_entry.py 纯逻辑单元测试（不依赖 pywebview/pystray）。"""

import os

import pytest

from exe_entry import (
    build_local_url,
    ensure_resource_path,
    pick_free_port,
    resolve_app_base,
)


def test_pick_free_port_returns_given_when_free(monkeypatch):
    monkeypatch.setattr("exe_entry._port_is_free", lambda port: True)
    assert pick_free_port(8000) == 8000


def test_pick_free_port_scans_upward(monkeypatch):
    taken = {8000, 8001}
    monkeypatch.setattr("exe_entry._port_is_free", lambda port: port not in taken)
    assert pick_free_port(8000) == 8002


def test_build_local_url():
    assert build_local_url("127.0.0.1", 8123) == "http://127.0.0.1:8123"


def test_resolve_app_base_meipass(monkeypatch):
    monkeypatch.setattr("exe_entry.sys._MEIPASS", "C:/tmp/_MEI12345", raising=False)
    assert resolve_app_base() == "C:/tmp/_MEI12345"


def test_resolve_app_base_source(monkeypatch):
    monkeypatch.delattr("exe_entry.sys._MEIPASS", raising=False)
    assert resolve_app_base() == os.path.dirname(os.path.abspath("exe_entry.py"))


def test_ensure_resource_path_meipass(monkeypatch):
    monkeypatch.setattr("exe_entry.sys._MEIPASS", "C:/tmp/_MEI12345", raising=False)
    assert ensure_resource_path("static", "style.css") == "C:/tmp/_MEI12345/static/style.css"


def test_ensure_resource_path_source(monkeypatch):
    monkeypatch.delattr("exe_entry.sys._MEIPASS", raising=False)
    base = os.path.dirname(os.path.abspath("exe_entry.py"))
    assert ensure_resource_path("static", "style.css") == os.path.join(base, "static", "style.css")
