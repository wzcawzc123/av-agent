"""桌面版文件下载与打开工具。"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from desktop.api import AvApi, ApiError

OUTPUT_ROOT = os.path.join(os.path.expanduser("~"), "AVAgent 输出")


def open_in_folder(path: str) -> None:
    folder = os.path.dirname(path) or "."
    try:
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass


def download_file(api: AvApi, server_path: str, project_id: Optional[int] = None) -> Optional[str]:
    """下载单个文件到本地输出目录；失败抛 ApiError。"""
    folder = os.path.join(OUTPUT_ROOT, f"项目{project_id or 0}")
    name = os.path.basename(server_path) or "file"
    local = os.path.join(folder, name)
    return api.download(server_path, local)


def download_many(api: AvApi, server_paths: list[str], project_id: Optional[int] = None) -> list[str]:
    ok: list[str] = []
    for path in server_paths:
        try:
            ok.append(download_file(api, path, project_id))
        except ApiError:
            continue
    return ok
