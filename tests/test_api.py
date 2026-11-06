"""The API client maps the contract of API.md onto Python."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from custom_components.d2ha.api import (
    D2HAAuthError,
    D2HAClient,
    D2HAConnectionError,
    D2HAError,
)

from conftest import CONTAINERS, INFO, TOKEN, URL

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client(aioclient_mock):
    session = aioclient_mock.create_session(asyncio.get_running_loop())
    yield D2HAClient(session, URL, TOKEN)
    await session.close()


async def test_info_ok(aioclient_mock, client):
    aioclient_mock.get(f"{URL}/api/v1/info", json=INFO)
    data = await client.info()
    assert data["counts"]["updates"] == 1


async def test_containers_uses_the_ha_filter(aioclient_mock, client):
    aioclient_mock.get(f"{URL}/api/v1/containers?ha=1", json=CONTAINERS)
    data = await client.containers()
    assert len(data["containers"]) == 3


async def test_wrong_token_raises_auth_error(aioclient_mock, client):
    aioclient_mock.get(
        f"{URL}/api/v1/info", status=401, json={"error": "unauthorized"}
    )
    with pytest.raises(D2HAAuthError):
        await client.info()


async def test_unreachable_server_raises_connection_error(aioclient_mock, client):
    aioclient_mock.get(
        f"{URL}/api/v1/info",
        exc=aiohttp.ClientConnectionError("refused"),
    )
    with pytest.raises(D2HAConnectionError):
        await client.info()


async def test_error_code_is_kept(aioclient_mock, client):
    aioclient_mock.post(
        f"{URL}/api/v1/update-all",
        status=409,
        json={"error": "nothing_to_update"},
    )
    with pytest.raises(D2HAError) as excinfo:
        await client.update_all()
    assert excinfo.value.code == "nothing_to_update"


async def test_bad_json_is_a_bad_response(aioclient_mock, client):
    aioclient_mock.get(f"{URL}/api/v1/info", text="this is not json")
    with pytest.raises(D2HAError) as excinfo:
        await client.info()
    assert excinfo.value.code == "error.bad_response"


async def test_notes_404_means_no_notes(aioclient_mock, client):
    aioclient_mock.get(
        f"{URL}/api/v1/containers/db/notes",
        status=404,
        json={"error": "no_notes"},
    )
    assert await client.notes("db") is None


async def test_update_returns_the_job_id(aioclient_mock, client):
    aioclient_mock.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        json={"id": "job123", "state": "queued"},
    )
    assert await client.update_container("media_jellyfin") == "job123"
