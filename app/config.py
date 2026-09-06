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


def _load_or_create_token() -> str:
    """访问口令：环境变量优先；否则读/建 data/access_token.txt，保证重启不变。"""
    env = os.environ.get("AV_ACCESS_TOKEN")
    if env:
        return env
    token_file = os.path.join(_base_dir(), "data", "access_token.txt")
    try:
        if os.path.exists(token_file):
            with open(token_file, encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token
        token = secrets.token_urlsafe(16)
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token)
        return token
    except OSError:
        return secrets.token_urlsafe(16)


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
    ACCESS_TOKEN: str = field(default_factory=lambda: _load_or_create_token())
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
