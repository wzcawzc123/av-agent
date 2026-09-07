"""后台 API 调用线程与 UI 辅助。"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

from desktop.api import ApiError


class ApiCallThread(QThread):
    """把同步 API 调用挪到后台线程，避免阻塞 UI。"""

    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            self.finished_ok.emit(self._fn())
        except ApiError as e:
            self.finished_err.emit(e.message)
        except Exception as e:  # noqa: BLE001
            self.finished_err.emit(str(e))


def run_api(
    parent: QObject,
    threads: list[ApiCallThread],
    fn: Callable[[], Any],
    ok: Callable[[Any], None],
    err: Optional[Callable[[str], None]] = None,
) -> None:
    """启动一个后台 API 调用；threads 用于追踪存活线程（避免被 GC 回收）。"""
    thread = ApiCallThread(fn, parent)
    thread.finished_ok.connect(ok)
    if err is not None:
        thread.finished_err.connect(err)
    threads[:] = [t for t in threads if not t.isFinished()] + [thread]
    thread.start()
