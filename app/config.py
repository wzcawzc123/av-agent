import os
import secrets
from dataclasses import dataclass, field


@dataclass
class Settings:
    base_dir: str = field(
        default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ACCESS_TOKEN: str = field(
        default_factory=lambda: os.environ.get("AV_ACCESS_TOKEN", secrets.token_urlsafe(16))
    )

    def __post_init__(self):
        self.DATA_DIR = os.path.join(self.base_dir, "data")
        self.OUTPUT_DIR = os.path.join(self.base_dir, "output")
        self.STATIC_DIR = os.path.join(self.base_dir, "static")
        self.UPLOAD_DIR = os.path.join(self.base_dir, "uploads")
        self.DB_PATH = os.path.join(self.DATA_DIR, "avagent.db")
        self.MASTER_KEY_PATH = os.path.join(self.DATA_DIR, "master.key")
        self.SECRETS_PATH = os.path.join(self.DATA_DIR, "secrets.bin")

    def ensure_dirs(self):
        for d in (self.DATA_DIR, self.OUTPUT_DIR, self.STATIC_DIR, self.UPLOAD_DIR):
            os.makedirs(d, exist_ok=True)


settings = Settings()
