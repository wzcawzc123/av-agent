from app.security.crypto import get_cipher, encrypt_text, decrypt_text


def test_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.security.crypto.KEY_PATH", str(tmp_path / "master.key"))
    c1 = get_cipher()
    token = encrypt_text("sk-abc123")
    assert token != "sk-abc123"
    assert decrypt_text(token) == "sk-abc123"


def test_key_file_created_with_600(tmp_path, monkeypatch):
    monkeypatch.setattr("app.security.crypto.KEY_PATH", str(tmp_path / "master.key"))
    get_cipher()
    mode = oct((tmp_path / "master.key").stat().st_mode & 0o777)
    assert mode == "0o600"
