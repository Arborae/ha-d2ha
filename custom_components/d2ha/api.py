"""Async client for the D2HA API.

The contract is API.md in Arborae/docker2homeassistant: base path /api/v1,
bearer token authentication, additive changes only. This client relies only on
what that file describes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_BASE, REQUEST_TIMEOUT


class D2HAError(Exception):
    """A D2HA request failed; ``code`` is the API error code when there is one."""

    def __init__(self, code: str = "error.generic") -> None:
        super().__init__(code)
        self.code = code


class D2HAAuthError(D2HAError):
    """The token is missing, wrong or revoked."""


class D2HAConnectionError(D2HAError):
    """D2HA cannot be reached."""


class D2HAClient:
    """Small wrapper around the D2HA endpoints the integration uses."""

    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _request(
        self, method: str, path: str, expect: tuple[int, ...] = (200,)
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.request(
                    method, f"{self.url}{API_BASE}{path}", headers=self._headers
                )
                payload: dict[str, Any] = await resp.json(content_type=None)
        except (ClientError, asyncio.TimeoutError) as exc:
            raise D2HAConnectionError("error.cannot_connect") from exc
        except (ValueError, TypeError) as exc:
            raise D2HAError("error.bad_response") from exc
        if resp.status == 401:
            raise D2HAAuthError("error.unauthorized")
        if resp.status not in expect:
            code = payload.get("error", f"error.http_{resp.status}")
            raise D2HAError(code)
        return payload

    async def info(self) -> dict[str, Any]:
        """Server version, check schedule and counters."""
        return await self._request("GET", "/info")

    async def containers(self) -> dict[str, Any]:
        """The containers shown in Home Assistant, with their update status."""
        return await self._request("GET", "/containers?ha=1")

    async def notes(self, key: str) -> dict[str, Any] | None:
        """Release notes of the pending update, None when there are none."""
        try:
            return await self._request("GET", f"/containers/{key}/notes")
        except D2HAError as exc:
            if exc.code in ("no_notes", "not_found"):
                return None
            raise

    async def jobs(self) -> list[dict[str, Any]]:
        """Jobs still queued or running."""
        payload = await self._request("GET", "/jobs")
        return payload.get("jobs", [])

    async def job(self, job_id: str) -> dict[str, Any] | None:
        """One job, None once D2HA has forgotten it."""
        try:
            return await self._request("GET", f"/jobs/{job_id}")
        except D2HAError as exc:
            if exc.code == "not_found":
                return None
            raise

    async def check_now(self) -> None:
        """Start an update check."""
        await self._request("POST", "/check", expect=(202,))

    async def update_container(self, key: str) -> str:
        """Start the update of one container; returns the job id."""
        payload = await self._request("POST", f"/containers/{key}/update", expect=(202,))
        return payload["id"]

    async def update_all(self) -> str:
        """Start the update of every container with an update; returns the job id."""
        payload = await self._request("POST", "/update-all", expect=(202,))
        return payload["id"]

    async def prune_images(self) -> str:
        """Start the cleanup of unused images; returns the job id."""
        payload = await self._request("POST", "/images/prune", expect=(202,))
        return payload["id"]
