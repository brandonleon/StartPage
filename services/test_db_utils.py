import os
import sqlite3
from pathlib import Path
from time import time
from uuid import uuid4

import pytest

TEST_CONFIG_PATH = Path(__file__).resolve().parent / "test_config.toml"
os.environ["STARTPAGE_CONFIG_PATH"] = str(TEST_CONFIG_PATH)

import services.db_utils as db_utils  # noqa: E402
from services import app_config  # noqa: E402


def setup_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def teardown_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def test_get_count():
    assert isinstance(db_utils.get_count()["count"], int)


def test_get_links():
    assert isinstance(db_utils.get_links(), list)
    assert isinstance(db_utils.get_links()[0]["id"], str)
    assert isinstance(db_utils.get_links()[0]["url"], str)
    assert isinstance(db_utils.get_links()[0]["name"], str)
    assert isinstance(db_utils.get_links()[0]["rank"], float)
    assert isinstance(db_utils.get_links()[0]["accessed"], str)


def test_get_frecency_config():
    config = db_utils.get_frecency_config()
    assert isinstance(config["batch_size"], int)
    assert config["batch_size"] > 0
    assert isinstance(config["max_rank"], int)
    assert config["max_rank"] >= 100


def test_purge_expired_links_removes_only_expired_rows():
    now = int(time())
    expired_name = f"Expired-{uuid4()}"
    future_name = f"Future-{uuid4()}"
    expired_id = db_utils.save_link(
        expired_name,
        f"https://example.com/{uuid4()}",
        expires_at=now - 10,
    )
    future_id = db_utils.save_link(
        future_name,
        f"https://example.com/{uuid4()}",
        expires_at=now + 3600,
    )

    removed = db_utils.purge_expired_links(now)
    assert removed >= 1

    con = sqlite3.connect(db_utils.db_path)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM links WHERE id = ?", (expired_id,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM links WHERE id = ?", (future_id,))
    assert cur.fetchone()[0] == 1

    con.close()
    db_utils.delete_link(future_id)


def test_temp_link_config_round_trip():
    original = db_utils.get_temp_link_config()
    updated = db_utils.update_temp_link_config(
        True,
        12,
        48,
        900,
    )
    assert updated["enabled"] is True
    assert updated["default_ttl_hours"] == 12
    assert updated["max_custom_hours"] == 48
    assert updated["purge_interval_seconds"] == 900
    db_utils.update_temp_link_config(
        original["enabled"],
        original["default_ttl_hours"],
        original["max_custom_hours"],
        original["purge_interval_seconds"],
    )


def test_save_link_duplicate_url_raises():
    url = f"https://duplicate-check.example/{uuid4()}"
    first_id = db_utils.save_link(f"Primary-{uuid4()}", url)
    with pytest.raises(db_utils.DuplicateLinkError):
        db_utils.save_link(f"Duplicate-{uuid4()}", url)
    db_utils.delete_link(first_id)


def test_find_link_by_url_returns_summary():
    name = f"Lookup-{uuid4()}"
    url = f"https://lookup.example/{uuid4()}"
    link_id = db_utils.save_link(name, url)
    summary = db_utils.find_link_by_url(url)
    assert summary is not None
    assert summary["id"] == link_id
    assert summary["name"] == name
    db_utils.delete_link(link_id)
