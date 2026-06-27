from pathlib import Path


def test_storage_dir_uses_vaya_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("VAYA_DATA_DIR", str(tmp_path))

    from paths import storage_dir

    assert storage_dir() == tmp_path


def test_config_path_uses_vaya_config_path(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    monkeypatch.setenv("VAYA_CONFIG_PATH", str(config_path))

    from paths import config_path as resolve_config_path

    assert resolve_config_path() == config_path


def test_default_storage_dir_stays_backend_local(monkeypatch):
    monkeypatch.delenv("VAYA_DATA_DIR", raising=False)

    from paths import storage_dir

    assert storage_dir() == Path(__file__).parent.parent / "storage"
