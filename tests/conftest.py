"""Shared fixtures: a fake D2HA server on the API contract of API.md."""

from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

URL = "http://d2ha.example:12021"
TOKEN = "test-token"

INFO = {
    "version": "0.4.1",
    "api": 1,
    "read_only": False,
    "docker": "28.4.0",
    "check": {"last": 1762448964.1, "next": 1762470564.1, "interval_hours": 6, "running": False},
    "counts": {"containers": 3, "running": 2, "updates": 1, "unused_images": 4},
}

CONTAINERS = {
    "containers": [
        {
            "key": "media_jellyfin",
            "id": "abc123",
            "name": "jellyfin",
            "stack": "media",
            "image": "jellyfin/jellyfin:latest",
            "image_id": "sha256:1",
            "state": "running",
            "status": "Up 3 days",
            "health": "",
            "created": 1762100000,
            "is_self": False,
            "is_proxy": False,
            "update": "available",
            "installed_version": "12.3",
            "latest_version": "12.4",
            "release_url": "https://github.com/jellyfin/jellyfin/releases/tag/v12.4",
            "has_notes": True,
            "breaking": False,
            "error": "",
            "ha": True,
            "can_update": True,
        },
        {
            "key": "monitoring_grafana",
            "id": "def456",
            "name": "grafana",
            "stack": "monitoring",
            "image": "grafana/grafana:latest",
            "image_id": "sha256:2",
            "state": "running",
            "status": "Up 3 days (healthy)",
            "health": "healthy",
            "created": 1762100000,
            "is_self": False,
            "is_proxy": False,
            "update": "current",
            "installed_version": "13.3.0",
            "latest_version": "13.3.0",
            "release_url": "",
            "has_notes": False,
            "breaking": False,
            "error": "",
            "ha": True,
            "can_update": False,
        },
        {
            "key": "db",
            "id": "ghi789",
            "name": "db",
            "stack": "",
            "image": "postgres:17",
            "image_id": "sha256:3",
            "state": "exited",
            "status": "Exited (0) 2 hours ago",
            "health": "",
            "created": 1762100000,
            "is_self": False,
            "is_proxy": False,
            "update": "pinned",
            "installed_version": "17",
            "latest_version": "17",
            "release_url": "",
            "has_notes": False,
            "breaking": False,
            "error": "",
            "ha": True,
            "can_update": False,
        },
    ],
    "checked_at": 1762448964.1,
    "checking": False,
}


def make_container(key: str, name: str, **overrides):
    """A container entry on the API contract; overrides change any field."""
    container = {
        "key": key,
        "id": f"id-{key}",
        "name": name,
        "stack": "",
        "image": f"{name}/{name}:latest",
        "image_id": "sha256:x",
        "state": "running",
        "status": "Up 1 day",
        "health": "",
        "created": 1762100000,
        "is_self": False,
        "is_proxy": False,
        "update": "current",
        "installed_version": "1.0",
        "latest_version": "1.0",
        "release_url": "",
        "has_notes": False,
        "breaking": False,
        "error": "",
        "ha": True,
        "can_update": False,
    }
    container.update(overrides)
    return container


def with_container(*extra) -> dict:
    """The CONTAINERS payload plus extra containers."""
    return {**CONTAINERS, "containers": [*CONTAINERS["containers"], *extra]}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the custom integration in every test."""
    yield


def register_d2ha(mock, info=INFO, containers=CONTAINERS, jobs=None):
    """Point the fake server at the given answers."""
    mock.get(f"{URL}/api/v1/info", json=info)
    mock.get(f"{URL}/api/v1/containers?ha=1", json=containers)
    mock.get(f"{URL}/api/v1/jobs", json={"jobs": jobs or []})


@pytest.fixture
def d2ha_server(aioclient_mock):
    """Intercept every HTTP call to the fake D2HA server."""
    register_d2ha(aioclient_mock)
    return aioclient_mock


async def setup_integration(hass, url=URL, token=TOKEN):
    """Create and set up a config entry against the fake server."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.d2ha.const import CONF_TOKEN, CONF_URL

    entry = MockConfigEntry(
        domain="d2ha", data={CONF_URL: url, CONF_TOKEN: token}, unique_id=url
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
