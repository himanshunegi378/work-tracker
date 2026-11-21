import pytest


@pytest.fixture(autouse=True)
def _no_cli_file_logging(monkeypatch):
    """Keep CLI tests from attaching a real log file handler to the root logger."""
    monkeypatch.setattr("src.cli.app._configure_cli_logging", lambda: None)


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """In-memory keyring so no test ever reads or writes the real OS vault."""
    import keyring
    import keyring.errors

    store = {}

    def get_password(service, name):
        return store.get((service, name))

    def set_password(service, name, value):
        store[(service, name)] = value

    def delete_password(service, name):
        if (service, name) not in store:
            raise keyring.errors.PasswordDeleteError("not found")
        del store[(service, name)]

    monkeypatch.setattr(keyring, "get_password", get_password)
    monkeypatch.setattr(keyring, "set_password", set_password)
    monkeypatch.setattr(keyring, "delete_password", delete_password)
    return store


@pytest.fixture(autouse=True)
def isolated_ipc_endpoint(tmp_path, monkeypatch):
    """Point the CLI at an empty endpoint file so tests never reach a real running app."""
    from src.core import ipc

    monkeypatch.setattr(ipc, "endpoint_path", lambda: tmp_path / "ipc-endpoint.json")
