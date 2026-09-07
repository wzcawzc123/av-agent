"""SSE 进度监听：在后台线程消费 /api/tasks/{id}/stream，转发 progress/done 事件。"""

from __future__ import annotations

import json

import httpx
from PySide6.QtCore import QThread, Signal


class ChatSseWorker(QThread):
    """消费 /api/agent/chat/stream 的 SSE 对话流。

    signals:
        token(text: str)       —— 流式文本增量
        tool(name: str, result: str) —— 工具调用通知
        done(need_config: bool, reply: str, project_id: int)
    """

    token = Signal(str)
    tool = Signal(str, str)
    done = Signal(bool, str, int)

    def __init__(self, base_url: str, payload: dict, parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._payload = payload
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # noqa: D102
        url = f"{self._base_url}/api/agent/chat/stream"
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("POST", url, json=self._payload) as resp:
                    if resp.status_code == 200:
                        for line in resp.iter_lines():
                            if self._stop:
                                return
                            if not line.startswith("data: "):
                                continue
                            try:
                                event = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue
                            etype = event.get("type")
                            if etype == "token":
                                self.token.emit(str(event.get("text", "")))
                            elif etype == "tool":
                                self.tool.emit(str(event.get("name", "")),
                                               str(event.get("result", "")))
                            elif etype == "done":
                                self.done.emit(
                                    bool(event.get("need_config")),
                                    str(event.get("reply", "")),
                                    int(event.get("project_id") or 0),
                                )
                                return
                    else:
                        self.done.emit(True, f"服务返回 HTTP {resp.status_code}", 0)
        except httpx.HTTPError as e:
            self.done.emit(True, f"连接失败：{e}", 0)
        except Exception as e:  # noqa: BLE001
            self.done.emit(True, str(e), 0)


class SseWorker(QThread):
    """监听单个生成任务的 SSE 流。

    signals:
        progress(percent: int, message: str)
        done(success: bool, error: str, result_json: str)
    """

    progress = Signal(int, str)
    done = Signal(bool, str, str)

    def __init__(self, base_url: str, task_id: str, parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._task_id = task_id
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # noqa: D102
        url = f"{self._base_url}/api/tasks/{self._task_id}/stream"
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        self.done.emit(False, f"HTTP {resp.status_code}", "")
                        return
                    for line in resp.iter_lines():
                        if self._stop:
                            return
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        etype = event.get("type")
                        if etype == "progress":
                            self.progress.emit(int(event.get("percent", 0) or 0),
                                               str(event.get("message", "")))
                        elif etype == "done":
                            ok = event.get("status") == "success"
                            error = str(event.get("error", ""))
                            result = json.dumps(event.get("result", {}), ensure_ascii=False)
                            self.done.emit(ok, error, result)
                            return
        except httpx.HTTPError as e:
            self.done.emit(False, f"连接失败：{e}", "")
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e), "")
