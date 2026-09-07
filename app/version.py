"""AV Agent 版本与更新检查。

客户端更新机制（配合 GitHub Releases）：
- 本地版本号见 VERSION；
- 前端「设置 → 软件更新」调用 /api/update/check；
- 后端读取更新配置（默认 GitHub Releases API），比较版本并返回
  最新版本、更新说明和下载地址；
- 私有仓库需要填 GitHub Token（只读 release 权限即可）。
"""
import re

APP_NAME = "AV Agent"
VERSION = "1.3.3"
REPO = "wzcawzc123/av-agent"
DEFAULT_CHECK_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(v: str) -> tuple:
    """'v1.2.3' / '1.2.3' / '1.2' → (1, 2, 3)；无法解析时返回 (0, 0, 0)。"""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(v or ""))
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def is_newer(latest: str, current: str) -> bool:
    """latest 版本号严格大于 current 时为 True（忽略前缀 v）。"""
    return parse_version(latest) > parse_version(current)
