"""Secrets referenced from config resolve from the operating system keyring."""
import json

import keyring
import pytest
from keyring.backend import KeyringBackend

from jarvis import secret_store
from jarvis.config import load_settings


class _MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        del self.store[(service, username)]


class _BrokenKeyring(KeyringBackend):
    priority = 1

    def get_password(self, service, username):
        raise RuntimeError("keyring locked")

    def set_password(self, service, username, password):
        raise RuntimeError("keyring locked")

    def delete_password(self, service, username):
        raise RuntimeError("keyring locked")


@pytest.fixture
def memory_keyring():
    previous = keyring.get_keyring()
    backend = _MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _write_config(tmp_path, monkeypatch, data):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("JARVIS_CONFIG_PATH", str(cfg_path))
    return cfg_path


@pytest.mark.unit
def test_literal_values_pass_through(memory_keyring):
    assert secret_store.resolve_secret("sk-plain") == "sk-plain"
    assert secret_store.resolve_secret("") == ""


@pytest.mark.unit
def test_stored_secret_round_trips_through_its_reference(memory_keyring):
    secret_store.set_secret("ha_token", "s3cret")
    reference = secret_store.reference_for("ha_token")
    assert secret_store.is_secret_reference(reference)
    assert secret_store.resolve_secret(reference) == "s3cret"


@pytest.mark.unit
def test_reference_may_name_another_service(memory_keyring):
    memory_keyring.set_password("other", "key", "value")
    assert secret_store.resolve_secret(f"{secret_store.SECRET_PREFIX}other/key") == "value"


@pytest.mark.unit
def test_missing_secret_resolves_empty_never_the_reference(memory_keyring):
    assert secret_store.resolve_secret(secret_store.reference_for("absent")) == ""


@pytest.mark.unit
def test_unavailable_keyring_resolves_empty():
    previous = keyring.get_keyring()
    keyring.set_keyring(_BrokenKeyring())
    try:
        assert secret_store.resolve_secret(secret_store.reference_for("x")) == ""
    finally:
        keyring.set_keyring(previous)


@pytest.mark.unit
def test_deleted_secret_no_longer_resolves(memory_keyring):
    secret_store.set_secret("gone", "v")
    assert secret_store.delete_secret("gone") is True
    assert secret_store.resolve_secret(secret_store.reference_for("gone")) == ""
    assert secret_store.delete_secret("gone") is False


@pytest.mark.unit
def test_settings_resolve_api_keys_and_mcp_values(memory_keyring, monkeypatch, tmp_path):
    secret_store.set_secret("llm", "llm-key")
    secret_store.set_secret("brave", "brave-key")
    secret_store.set_secret("ha_token", "ha-key")
    ref = secret_store.reference_for
    cfg_path = _write_config(tmp_path, monkeypatch, {
        "llm_provider": "openai_compatible",
        "llm_api_key": ref("llm"),
        "embedding_api_key": "literal-embed",
        "brave_search_api_key": ref("brave"),
        "mcps": {
            "home_assistant": {
                "command": "mcp-proxy",
                "args": ["--headers", "Authorization", ref("ha_token")],
                "env": {"API_ACCESS_TOKEN": ref("ha_token"), "PLAIN": "x"},
            }
        },
    })
    s = load_settings()

    assert s.llm_api_key == "llm-key"
    assert s.embedding_api_key == "literal-embed"
    assert s.brave_search_api_key == "brave-key"
    server = s.mcps["home_assistant"]
    assert server["env"] == {"API_ACCESS_TOKEN": "ha-key", "PLAIN": "x"}
    assert server["args"][-1] == "ha-key"
    # The file on disk keeps the references; secrets never land in it.
    on_disk = cfg_path.read_text(encoding="utf-8")
    saved = json.loads(on_disk)
    assert saved["llm_api_key"] == ref("llm")
    assert saved["mcps"]["home_assistant"]["env"]["API_ACCESS_TOKEN"] == ref("ha_token")
    for secret in ("llm-key", "brave-key", "ha-key"):
        assert secret not in on_disk


@pytest.mark.unit
def test_cli_stores_secret_from_hidden_prompt(memory_keyring, monkeypatch, capsys):
    monkeypatch.setattr(secret_store.getpass, "getpass", lambda prompt="": "typed")
    assert secret_store.main(["set", "ha_token"]) == 0
    out = capsys.readouterr().out
    assert "typed" not in out
    assert secret_store.reference_for("ha_token") in out
    assert secret_store.resolve_secret(secret_store.reference_for("ha_token")) == "typed"


@pytest.mark.unit
def test_cli_rejects_empty_secret(memory_keyring, monkeypatch):
    monkeypatch.setattr(secret_store.getpass, "getpass", lambda prompt="": "")
    assert secret_store.main(["set", "ha_token"]) == 1
    assert secret_store.resolve_secret(secret_store.reference_for("ha_token")) == ""
