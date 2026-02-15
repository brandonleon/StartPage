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


def test_metrics_whitelist_round_trip():
    original = db_utils.get_metrics_whitelist()
    updated = db_utils.update_metrics_whitelist(["10.0.0.0/8", "192.168.1.10"])
    assert updated == ["10.0.0.0/8", "192.168.1.10/32"]
    assert db_utils.is_ip_allowed_for_metrics("10.12.0.5") is True
    assert db_utils.is_ip_allowed_for_metrics("192.168.1.10") is True
    assert db_utils.is_ip_allowed_for_metrics("8.8.8.8") is False
    db_utils.update_metrics_whitelist(original)


def test_metrics_whitelist_rejects_invalid_entries():
    with pytest.raises(ValueError):
        db_utils.update_metrics_whitelist(["not-an-ip"])


def test_trusted_proxy_cidrs_round_trip():
    original = db_utils.get_trusted_proxy_cidrs()
    try:
        updated = db_utils.update_trusted_proxy_cidrs(
            ["172.17.0.1", "10.0.0.0/24", "172.17.0.1/32"]
        )
        assert updated == ["172.17.0.1/32", "10.0.0.0/24"]
    finally:
        db_utils.update_trusted_proxy_cidrs(original)


def test_trusted_proxy_cidrs_reject_invalid_entries():
    with pytest.raises(ValueError):
        db_utils.normalize_trusted_proxy_cidrs(["invalid-cidr"])


def test_metrics_runtime_counters_increment():
    original_requests = db_utils.get_metadata_value("metrics_requests_total")
    original_denied = db_utils.get_metadata_value("metrics_denied_total")
    try:
        db_utils.set_metadata_value("metrics_requests_total", "0")
        db_utils.set_metadata_value("metrics_denied_total", "0")

        counters = db_utils.increment_metrics_runtime_counters(denied=False)
        assert counters["requests_total"] == 1
        assert counters["denied_total"] == 0

        counters = db_utils.increment_metrics_runtime_counters(denied=True)
        assert counters["requests_total"] == 2
        assert counters["denied_total"] == 1
    finally:
        if original_requests is None:
            db_utils.set_metadata_value("metrics_requests_total", "0", overwrite=False)
        else:
            db_utils.set_metadata_value("metrics_requests_total", original_requests)
        if original_denied is None:
            db_utils.set_metadata_value("metrics_denied_total", "0", overwrite=False)
        else:
            db_utils.set_metadata_value("metrics_denied_total", original_denied)


def test_metrics_whitelist_add_entries_merges_without_replacing():
    original = db_utils.get_metrics_whitelist()
    db_utils.update_metrics_whitelist(["127.0.0.1/32"])
    try:
        updated = db_utils.add_metrics_whitelist_entries(
            ["10.0.0.0/8", "192.168.1.10", "10.0.0.0/8"]
        )
        assert updated == ["127.0.0.1/32", "10.0.0.0/8", "192.168.1.10/32"]
    finally:
        db_utils.update_metrics_whitelist(original)


def test_metrics_whitelist_remove_entries_uses_normalized_values():
    original = db_utils.get_metrics_whitelist()
    db_utils.update_metrics_whitelist(["127.0.0.1/32", "10.0.0.0/8", "192.168.1.10/32"])
    try:
        updated = db_utils.remove_metrics_whitelist_entries(["192.168.1.10", "10.0.0.0/8"])
        assert updated == ["127.0.0.1/32"]
    finally:
        db_utils.update_metrics_whitelist(original)
