import json
import sqlite3
from uuid import uuid4

import httpx
import pytest

import main
import services.db_utils as db_utils


@pytest.fixture
def export_link():
    name = f"ExportRoute-{uuid4()}"
    url = f"https://route-export.example/{uuid4()}"
    link_id = db_utils.save_link(name, url)
    tag = f"route-tag-{uuid4().hex[:6]}"
    db_utils.add_tag_to_link(link_id, tag)
    yield {"id": link_id, "tag": tag, "name": name}
    db_utils.delete_link(link_id)


def _cleanup_link(link_id: str):
    tags = db_utils.get_tags_for_link(link_id)
    for tag in tags:
        db_utils.remove_tag_from_link(link_id, tag["id"])
    db_utils.delete_link(link_id)


@pytest.mark.anyio
async def test_exports_json_route_returns_payload(export_link):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/exports/json")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.json"')
    payload = response.json()
    match = next(item for item in payload if item["id"] == export_link["id"])
    assert match["name"] == export_link["name"]
    assert export_link["tag"] in match["tags"]


@pytest.mark.anyio
async def test_exports_csv_route_streams_attachment(export_link):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/exports/csv")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.csv"')
    lines = response.text.splitlines()
    assert lines[0] == "id,name,url,rank,accessed,tags"
    assert any(export_link["tag"] in line for line in lines[1:])


@pytest.mark.anyio
async def test_exports_invalid_format_returns_400():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/exports/yaml")
    assert response.status_code == 400
    assert json.loads(response.content).get("detail")


@pytest.mark.anyio
async def test_import_route_creates_link_from_csv():
    unique_name = f"Route Import {uuid4().hex[:6]}"
    csv_payload = f"id,name,url,rank,accessed,tags\n,{unique_name},https://route-import.example/,3.1,1700000001,route-tag".encode(
        "utf-8"
    )
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/imports",
            data={"format": "csv"},
            files={"upload": ("links.csv", csv_payload, "text/csv")},
        )
    assert response.status_code == 303
    created = db_utils.find_link_by_name(unique_name)
    assert created is not None
    tags = db_utils.get_tags_for_link(created["id"])
    assert any(tag["name"] == "route-tag" for tag in tags)
    _cleanup_link(created["id"])


@pytest.mark.anyio
async def test_import_route_updates_existing_json():
    original_name = f"Import Route Existing {uuid4().hex[:6]}"
    link_id = db_utils.save_link(original_name, f"https://import-existing.example/{uuid4()}")
    db_utils.add_tag_to_link(link_id, "legacy-tag")
    payload = json.dumps(
        [
            {
                "id": link_id,
                "name": "Import Route Updated",
                "url": "https://import-existing.example/updated",
                "rank": 12.5,
                "accessed": 1900000000,
                "tags": ["route-updated"],
            }
        ]
    ).encode("utf-8")
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/imports",
            data={"format": "json"},
            files={"upload": ("links.json", payload, "application/json")},
        )
    assert response.status_code == 303
    con = sqlite3.connect(db_utils.db_path)
    cur = con.cursor()
    cur.execute("SELECT name, url, rank, accessed FROM links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    con.close()
    assert row[0] == "Import Route Updated"
    assert row[1] == "https://import-existing.example/updated"
    assert abs(row[2] - 12.5) < 0.01
    assert row[3] == 1900000000
    tags = {tag["name"] for tag in db_utils.get_tags_for_link(link_id)}
    assert tags == {"route-updated"}
    _cleanup_link(link_id)
