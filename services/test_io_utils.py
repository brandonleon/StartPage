import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

TEST_CONFIG_PATH = Path(__file__).resolve().parent / "test_config.toml"
os.environ["STARTPAGE_CONFIG_PATH"] = str(TEST_CONFIG_PATH)

import services.db_utils as db_utils  # noqa: E402
from services import app_config  # noqa: E402
from services import io_utils  # noqa: E402


def setup_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def teardown_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def _create_link_with_tag(tag: str = "export-check"):
    name = f"Export-{uuid4()}"
    url = f"https://export.example/{uuid4()}"
    link_id = db_utils.save_link(name, url)
    db_utils.add_tag_to_link(link_id, tag)
    return link_id, name, tag


def _cleanup_link(link_id: str):
    tags = db_utils.get_tags_for_link(link_id)
    for tag in tags:
        db_utils.remove_tag_from_link(link_id, tag["id"])
    db_utils.delete_link(link_id)


def test_export_db_links_yields_rows_with_tags():
    link_id, name, tag = _create_link_with_tag()
    rows = io_utils.export_db_links()
    try:
        collected = None
        for row in rows:
            if row["id"] == link_id:
                collected = row
                break
        assert collected is not None
        assert collected["name"] == name
        assert tag in collected["tags"]
    finally:
        db_utils.delete_link(link_id)


def test_export_db_links_serializes_csv_and_json():
    link_id, name, tag = _create_link_with_tag("export-serialized")
    try:
        csv_payload = b"".join(io_utils.export_db_links("csv")).decode("utf-8")
        assert "id,name,url,rank,accessed,tags" in csv_payload.splitlines()[0]
        assert name in csv_payload
        assert tag in csv_payload

        json_payload = b"".join(io_utils.export_db_links("json")).decode("utf-8")
        data = json.loads(json_payload)
        match = next(item for item in data if item["id"] == link_id)
        assert match["name"] == name
        assert match["tags"] and tag in match["tags"]
    finally:
        db_utils.delete_link(link_id)


def test_import_db_links_creates_rows_from_json():
    unique_tag = f"import-json-{uuid4().hex[:6]}"
    url = f"https://json-import.example/{uuid4()}"
    payload = json.dumps(
        [
            {
                "id": "",
                "name": "JSON Import",
                "url": url,
                "rank": 4.2,
                "accessed": 1700000000,
                "tags": [unique_tag],
            }
        ]
    ).encode("utf-8")
    summary = io_utils.import_db_links(payload, "json")
    assert summary["created"] == 1
    record = db_utils.find_link_by_name("JSON Import")
    assert record is not None
    tags = db_utils.get_tags_for_link(record["id"])
    assert any(tag["name"] == unique_tag for tag in tags)
    _cleanup_link(record["id"])


def test_import_db_links_updates_existing_via_csv():
    link_id = db_utils.save_link("CSV Import Original", f"https://csv-import.example/{uuid4()}")
    db_utils.add_tag_to_link(link_id, "old-tag")
    csv_text = (
        "id,name,url,rank,accessed,tags\n"
        f"{link_id},CSV Import Updated,https://csv-import.example/updated,99.5,1700001000,new-tag;second-tag\n"
    )
    summary = io_utils.import_db_links(csv_text.encode("utf-8"), "csv")
    assert summary["updated"] == 1

    con = sqlite3.connect(db_utils.db_path)
    cur = con.cursor()
    cur.execute("SELECT name, url, rank, accessed FROM links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    con.close()
    assert row[0] == "CSV Import Updated"
    assert abs(row[2] - 99.5) < 0.001
    assert row[3] == 1700001000
    tags = {tag["name"] for tag in db_utils.get_tags_for_link(link_id)}
    assert tags == {"new-tag", "second-tag"}
    _cleanup_link(link_id)
