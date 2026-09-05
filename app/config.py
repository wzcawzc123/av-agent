import os
import secrets
import sys
from dataclasses import dataclass, field


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _base_dir() -> str:
    """数据目录：exe 模式下放在 exe 旁边（用户可写），源码模式下为项目根目录。"""
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _static_dir(base_dir: str) -> str:
    """静态资源：exe 模式下解压在 _MEIPASS 临时目录，源码模式下为 base_dir/static。"""
    if _is_frozen():
        return os.path.join(getattr(sys, "_MEIPASS", base_dir), "static")
    return os.path.join(base_dir, "static")


@dataclass
class Settings:
    base_dir: str = field(default_factory=_base_dir)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ACCESS_TOKEN: str = field(
        default_factory=lambda: os.environ.get("AV_ACCESS_TOKEN", secrets.token_urlsafe(16))
    )
    DATABASE_URL: str | None = field(
        default_factory=lambda: os.environ.get("AV_DATABASE_URL")
    )
    REDIS_URL: str | None = field(
        default_factory=lambda: os.environ.get("AV_REDIS_URL")
    )
    ENV: str = field(default_factory=lambda: os.environ.get("AV_ENV", "dev"))

    def __post_init__(self):
        self.DATA_DIR = os.path.join(self.base_dir, "data")
        self.OUTPUT_DIR = os.path.join(self.base_dir, "output")
        self.STATIC_DIR = _static_dir(self.base_dir)
        self.UPLOAD_DIR = os.path.join(self.base_dir, "uploads")
        self.DB_PATH = os.path.join(self.DATA_DIR, "avagent.db")
        self.MASTER_KEY_PATH = os.path.join(self.DATA_DIR, "master.key")
        self.SECRETS_PATH = os.path.join(self.DATA_DIR, "secrets.bin")

    def ensure_dirs(self):
        for d in (self.DATA_DIR, self.OUTPUT_DIR, self.STATIC_DIR, self.UPLOAD_DIR):
            os.makedirs(d, exist_ok=True)


settings = Settings()
