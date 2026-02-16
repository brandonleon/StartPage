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


@pytest.mark.anyio
async def test_edit_route_saves_new_tags_from_main_form():
    original_name = f"EditTagFlow-{uuid4()}"
    original_url = f"https://edit-tag-flow.example/{uuid4()}"
    link_id = db_utils.save_link(original_name, original_url)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/edit/{link_id}",
            data={
                "link_name": f"{original_name}-updated",
                "link_url": original_url,
                "tag_names": "team docs, Release-Notes",
                "temporary_preset": "default",
            },
        )
    assert response.status_code == 302
    tags = {tag["name"] for tag in db_utils.get_tags_for_link(link_id)}
    assert {"team-docs", "release-notes"}.issubset(tags)

    db_utils.delete_link(link_id)


@pytest.mark.anyio
async def test_quick_add_tag_redirects_back_to_edit_page():
    link_name = f"QuickTag-{uuid4()}"
    link_url = f"https://quick-tag.example/{uuid4()}"
    link_id = db_utils.save_link(link_name, link_url)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/link/{link_id}/tag",
            data={"tag_name": "quick-add"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == f"/edit/{link_id}"
    tags = {tag["name"] for tag in db_utils.get_tags_for_link(link_id)}
    assert "quick-add" in tags

    db_utils.delete_link(link_id)


@pytest.mark.anyio
async def test_edit_route_can_attach_existing_tag_to_untagged_link():
    shared_tag = f"shared-tag-{uuid4().hex[:6]}"
    source_id = db_utils.save_link(
        f"TagSource-{uuid4()}",
        f"https://tag-source.example/{uuid4()}",
    )
    target_name = f"TagTarget-{uuid4()}"
    target_url = f"https://tag-target.example/{uuid4()}"
    target_id = db_utils.save_link(target_name, target_url)
    db_utils.add_tag_to_link(source_id, shared_tag)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/edit/{target_id}",
            data={
                "link_name": target_name,
                "link_url": target_url,
                "tag_names": f"{shared_tag}, ",
                "temporary_preset": "default",
            },
        )
    assert response.status_code == 302
    target_tags = {tag["name"] for tag in db_utils.get_tags_for_link(target_id)}
    assert shared_tag in target_tags

    db_utils.delete_link(source_id)
    db_utils.delete_link(target_id)


@pytest.mark.anyio
async def test_edit_route_duplicate_name_or_url_returns_validation_error():
    link_a_name = f"EditDuplicateA-{uuid4()}"
    link_a_url = f"https://edit-duplicate-a.example/{uuid4()}"
    link_a_id = db_utils.save_link(link_a_name, link_a_url)

    link_b_name = f"EditDuplicateB-{uuid4()}"
    link_b_url = f"https://edit-duplicate-b.example/{uuid4()}"
    link_b_id = db_utils.save_link(link_b_name, link_b_url)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/edit/{link_b_id}",
            data={
                "link_name": link_b_name,
                "link_url": link_a_url,
                "tag_names": "should-not-save",
                "temporary_preset": "default",
            },
        )
    assert response.status_code == 400
    assert "already exists" in response.text
    tags = {tag["name"] for tag in db_utils.get_tags_for_link(link_b_id)}
    assert "should-not-save" not in tags

    db_utils.delete_link(link_a_id)
    db_utils.delete_link(link_b_id)
