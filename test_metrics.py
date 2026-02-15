import os

import httpx
import pytest

import main
import services.db_utils as db_utils


@pytest.fixture(autouse=True)
def _restore_metrics_whitelist():
    original = db_utils.get_metrics_whitelist()
    yield
    db_utils.update_metrics_whitelist(original)


@pytest.fixture(autouse=True)
def _restore_trusted_proxy_cidrs_env():
    original = os.environ.get("STARTPAGE_TRUSTED_PROXY_CIDRS")
    yield
    if original is None:
        os.environ.pop("STARTPAGE_TRUSTED_PROXY_CIDRS", None)
    else:
        os.environ["STARTPAGE_TRUSTED_PROXY_CIDRS"] = original


@pytest.mark.anyio
async def test_metrics_route_allows_localhost_when_whitelisted():
    db_utils.update_metrics_whitelist(["127.0.0.1/32"])
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "startpage_links_total" in response.text
    assert "startpage_metrics_requests_total" in response.text


@pytest.mark.anyio
async def test_metrics_route_denies_non_whitelisted_client():
    db_utils.update_metrics_whitelist(["10.0.0.0/8"])
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")
    assert response.status_code == 403
    assert response.json()["detail"] == "Metrics access denied for this IP."


@pytest.mark.anyio
async def test_metrics_route_uses_forwarded_for_header():
    db_utils.update_metrics_whitelist(["10.0.0.0/8"])
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics", headers={"x-forwarded-for": "10.1.2.3"})
    assert response.status_code == 200
    assert "startpage_metrics_whitelist_entries" in response.text


@pytest.mark.anyio
async def test_metrics_route_prefers_real_ip_header():
    db_utils.update_metrics_whitelist(["10.0.0.0/8"])
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/metrics",
            headers={"x-forwarded-for": "127.0.0.1", "x-real-ip": "10.9.8.7"},
        )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_metrics_route_ignores_forwarded_headers_from_untrusted_client():
    db_utils.update_metrics_whitelist(["10.0.0.0/8"])
    transport = httpx.ASGITransport(app=main.app, client=("198.51.100.25", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics", headers={"x-forwarded-for": "10.1.2.3"})
    assert response.status_code == 403


@pytest.mark.anyio
async def test_metrics_route_uses_forwarded_headers_from_configured_proxy():
    os.environ["STARTPAGE_TRUSTED_PROXY_CIDRS"] = "172.18.0.0/16"
    db_utils.update_metrics_whitelist(["10.0.0.0/8"])
    transport = httpx.ASGITransport(app=main.app, client=("172.18.0.10", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics", headers={"x-forwarded-for": "10.1.2.3"})
    assert response.status_code == 200
