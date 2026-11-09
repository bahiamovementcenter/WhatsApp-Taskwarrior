from pathlib import Path

import pytest

from whatsapp_taskwarrior import config


def write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "wtw.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_chats_env_adds_chats(tmp_path):
    p = write(tmp_path, '[whatsapp]\nmessages_db = "m.db"\nchats_env = "WTW_TEST_CHATS"\n')
    cfg = config.load(p, environ={"WTW_TEST_CHATS": "1@g.us=Team, 2@g.us"})
    assert cfg.chats == {"1@g.us": "Team", "2@g.us": "2@g.us"}


def test_chats_env_unset_means_no_chats(tmp_path):
    p = write(tmp_path, '[whatsapp]\nmessages_db = "m.db"\nchats_env = "WTW_TEST_CHATS"\n')
    assert config.load(p, environ={}).chats == {}


def test_chats_env_merges_with_table(tmp_path):
    p = write(
        tmp_path,
        '[whatsapp]\nmessages_db = "m.db"\nchats_env = "V"\n[whatsapp.chats]\n"1@g.us" = "File"\n',
    )
    assert config.load(p, environ={"V": "2@g.us=Env"}).chats == {"1@g.us": "File", "2@g.us": "Env"}


def test_chats_env_rejects_non_jid(tmp_path):
    p = write(tmp_path, '[whatsapp]\nmessages_db = "m.db"\nchats_env = "V"\n')
    with pytest.raises(config.ConfigError):
        config.load(p, environ={"V": "BMC-Neo"})
