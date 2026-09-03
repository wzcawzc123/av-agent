"""方案工具引擎注册表。"""

_ENGINES = ["deviation", "meeting", "broadcast", "led"]


def list_engines() -> list[str]:
    return list(_ENGINES)
