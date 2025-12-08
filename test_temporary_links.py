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
