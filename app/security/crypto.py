import os

from cryptography.fernet import Fernet

KEY_PATH = None  # 由 main 启动时注入 settings.MASTER_KEY_PATH


def _ensure_key_path():
    global KEY_PATH
    if KEY_PATH is None:
        from app.config import settings

        KEY_PATH = settings.MASTER_KEY_PATH
    return KEY_PATH


def get_cipher():
    path = _ensure_key_path()
    if not os.path.exists(path):
        key = Fernet.generate_key()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    with open(path, "rb") as f:
        return Fernet(f.read().strip())


def encrypt_text(plain: str) -> str:
    return get_cipher().encrypt(plain.encode()).decode()


def decrypt_text(token: str) -> str:
    return get_cipher().decrypt(token.encode()).decode()


ENC_PREFIX = "enc:"


def encrypt_secret(plain: str) -> str:
    """秘密字段落盘加密；空串原样返回（不加密）。"""
    if not plain:
        return plain
    return ENC_PREFIX + encrypt_text(plain)


def decrypt_secret(value: str) -> str:
    """读取秘密字段：enc: 前缀解密，否则按旧明文原样返回（向前兼容）。"""
    if not value or not value.startswith(ENC_PREFIX):
        return value
    try:
        return decrypt_text(value[len(ENC_PREFIX):])
    except Exception:
        return value  # master key 丢失等场景不阻塞启动
