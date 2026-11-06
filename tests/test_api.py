"""The API client maps the contract of API.md onto Python."""

from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.d2ha.api import (
    D2HAAuthError,
    D2HAClient,
    D2HAConnectionError,
    D2HAError,
)

from conftest import CONTAINERS, INFO, TOKEN, URL

pytestmark = pytest.mark.asyncio


async def make_client(mock):
    session = aiohttp.ClientSession()
    return D2HAClient(session, URL, TOKEN)


async def test_info_ok():
    with aioresponses() as mock:
        mock.get(f"{URL}/api/v1/info", payload=INFO)
        client = await make_client(mock)
        data = await client.info()
        assert data["counts"]["updates"] == 1
        await client._session.close()


async def test_containers_uses_the_ha_filter():
    with aioresponses() as mock:
        mock.get(f"{URL}/api/v1/containers?ha=1", payload=CONTAINERS)
        client = await make_client(mock)
        data = await client.containers()
        assert len(data["containers"]) == 3
        await client._session.close()


async def test_wrong_token_raises_auth_error():
    with aioresponses() as mock:
        mock.get(f"{URL}/api/v1/info", status=401, payload={"error": "unauthorized"})
        client = await make_client(mock)
        with pytest.raises(D2HAAuthError):
            await client.info()
        await client._session.close()


async def test_unreachable_server_raises_connection_error():
    with aioresponses() as mock:
        mock.get(
            f"{URL}/api/v1/info",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        client = await make_client(mock)
        with pytest.raises(D2HAConnectionError):
            await client.info()
        await client._session.close()


async def test_error_code_is_kept():
    with aioresponses() as mock:
        mock.post(
            f"{URL}/api/v1/update-all",
            status=409,
            payload={"error": "nothing_to_update"},
        )
        client = await make_client(mock)
        with pytest.raises(D2HAError) as excinfo:
            await client.update_all()
        assert excinfo.value.code == "nothing_to_update"
        await client._session.close()


async def test_notes_404_means_no_notes():
    with aioresponses() as mock:
        mock.get(
            f"{URL}/api/v1/containers/db/notes",
            status=404,
            payload={"error": "no_notes"},
        )
        client = await make_client(mock)
        assert await client.notes("db") is None
        await client._session.close()


async def test_update_returns_the_job_id():
    with aioresponses() as mock:
        mock.post(
            f"{URL}/api/v1/containers/media_jellyfin/update",
            status=202,
            payload={"id": "job123", "state": "queued"},
        )
        client = await make_client(mock)
        assert await client.update_container("media_jellyfin") == "job123"
        await client._session.close()
