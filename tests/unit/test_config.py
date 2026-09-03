import os
from app.config import Settings

def test_settings_defaults(tmp_path):
    s = Settings(base_dir=str(tmp_path))
    assert s.DB_PATH == str(tmp_path / "data" / "avagent.db")
    assert s.OUTPUT_DIR == str(tmp_path / "output")
    assert s.PORT == 8000
    assert len(s.ACCESS_TOKEN) >= 8

def test_settings_creates_dirs(tmp_path):
    s = Settings(base_dir=str(tmp_path))
    s.ensure_dirs()
    assert os.path.isdir(tmp_path / "data")
    assert os.path.isdir(tmp_path / "output")
    assert os.path.isdir(tmp_path / "static")
