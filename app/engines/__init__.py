"""方案工具引擎注册表。

新增引擎只需在实现模块中调用 register_engine() 注册执行函数与摘要函数，
chat 意图触发、/api/engines/* 端点与引擎清单将自动生效，无需再改多处。
"""

_REGISTRY: dict[str, dict] = {}


def register_engine(name: str, runner, summarizer=None) -> None:
    """注册引擎：runner(params)->result；summarizer(result)->str 可选。"""
    _REGISTRY[name] = {"runner": runner, "summarizer": summarizer}


def list_engines() -> list[str]:
    return list(_REGISTRY)


def get_runner(name: str):
    entry = _REGISTRY.get(name)
    return entry["runner"] if entry else None


def get_summarizer(name: str):
    entry = _REGISTRY.get(name)
    return entry["summarizer"] if entry else None
