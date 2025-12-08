from time import time
from uuid import uuid4

import httpx
import pytest

import main
import services.db_utils as db_utils


@pytest.mark.anyio
async def test_expired_links_are_not_returned_in_search():
    now = int(time())
    expired_name = f"TemporaryExpired-{uuid4()}"
    surviving_name = f"TemporarySurvivor-{uuid4()}"
    expired_id = db_utils.save_link(
        expired_name,
        f"https://example.com/{uuid4()}",
        expires_at=now - 5,
    )
    survivor_id = db_utils.save_link(
        surviving_name,
        f"https://example.com/{uuid4()}",
        expires_at=now + 3600,
    )

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/search?text={expired_name}")
        assert response.status_code == 200
        assert f"/redirect/{expired_id}" not in response.text

    db_utils.delete_link(survivor_id)


@pytest.mark.anyio
async def test_duplicate_link_submission_returns_error():
    existing_url = f"https://duplicate-submit.example/{uuid4()}"
    existing_name = f"DuplicateSubmit-{uuid4()}"
    existing_id = db_utils.save_link(existing_name, existing_url)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/add",
            data={
                "link_name": existing_name,
                "link_url": existing_url,
                "tag_names": "",
                "temporary_preset": "default",
            },
        )
    assert response.status_code == 400
    assert "already exists" in response.text

    db_utils.delete_link(existing_id)


@pytest.mark.anyio
async def test_duplicate_check_endpoint_returns_existing_details():
    name = f"DuplicateCheck-{uuid4()}"
    url = f"https://duplicate-check.example/{uuid4()}"
    link_id = db_utils.save_link(name, url)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/duplicates/check?field=url&link_url={url}")
        assert response.status_code == 200
        assert "Edit existing link" in response.text

        response_none = await client.get("/duplicates/check?field=url&link_url=https://unused.example/")
        assert response_none.status_code == 200
        assert response_none.text.strip() == ""

    db_utils.delete_link(link_id)
