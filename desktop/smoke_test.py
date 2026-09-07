"""桌面版 offscreen 冒烟测试：后端线程 + 主窗口 + API 联调 + 主题/会话/Agent 模式，2.5 秒后自动退出。"""

import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

settings.ensure_dirs()
settings.PORT = 8123 if settings.PORT == 8000 else settings.PORT

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop.api import AvApi
from desktop.main import start_server, wait_until_ready
from desktop.main_window import MainWindow
from desktop.theme import apply_theme, load_theme_pref, system_dark

base_url = f"http://127.0.0.1:{settings.PORT}"
stop = threading.Event()
threading.Thread(target=start_server, args=(stop,), daemon=True).start()
assert wait_until_ready(base_url, timeout=15), "服务未就绪"

api = AvApi(base_url=base_url)

# 1) API 联调
health = api.health()
print("health:", health.get("status"), health.get("version"))
providers = api.list_providers()
print("providers:", len(providers))
chat = api.chat("做一个 200 平的会议室方案")
print("chat:", chat.get("status"), "pid", chat.get("project_id"), "reply:", chat.get("reply", "")[:30])
# Agent 模式端点（未配模型 → need_config 提示）
agent = api.agent_chat("帮我查产品库的会议话筒")
print("agent chat:", agent.get("need_config"), agent.get("reply", "")[:40])
# 知识库预置生效
knowledge = api.list_knowledge()
docs = knowledge.get("documents", [])
print("knowledge docs:", len(docs), [d["title"][:12] for d in docs[:3]])
# 记忆工具注入的 MEMORY.md 不阻塞

# 2) 主窗口 + 主题
app = QApplication([])
dark = load_theme_pref()
apply_theme(app, dark)
print("theme applied (dark=%s, system_dark=%s)" % (dark, system_dark()))
win = MainWindow(api, app_version="smoke")
win.show()
# 切到对话页并验证页面对象
win.pages["chat"].mode_combo.setCurrentIndex(1)
print("chat mode:", win.pages["chat"].mode_combo.currentData())
QTimer.singleShot(2000, app.quit)
rc = app.exec()
print("window exec rc:", rc)

stop.set()
api.close()
print("SMOKE OK")
