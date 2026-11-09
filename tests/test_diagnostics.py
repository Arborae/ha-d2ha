"""Diagnostics: everything a bug report needs, nothing private."""

from __future__ import annotations

import json

import pytest

from conftest import INFO, TOKEN, URL, register_d2ha, setup_integration

pytestmark = pytest.mark.asyncio


async def test_diagnostics(hass, d2ha_server):
    """Entry redacted, /info as the coordinator has it, slim containers."""
    from custom_components.d2ha.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = await setup_integration(hass)
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["entry"] == {"url": "**REDACTED**", "token": "**REDACTED**"}
    assert data["info"] == INFO
    by_key = {c["key"]: c for c in data["containers"]}
    assert set(by_key) == {"media_jellyfin", "monitoring_grafana", "db"}
    assert by_key["media_jellyfin"] == {
        "key": "media_jellyfin",
        "state": "running",
        "health": "",
        "update": "available",
        "can_update": True,
        "has_notes": True,
        "breaking": False,
        "is_self": False,
        "is_proxy": False,
        "ha": True,
    }


async def test_the_running_job_is_listed_without_its_label(hass, d2ha_server):
    """An active update job shows, but its label (a container name) does not."""
    from custom_components.d2ha.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    d2ha_server.clear_requests()
    register_d2ha(
        d2ha_server,
        jobs=[
            {
                "id": "j1",
                "kind": "update_all",
                "state": "running",
                "label": "grafana",
                "percent": 88,
            }
        ],
    )
    entry = await setup_integration(hass)
    data = await async_get_config_entry_diagnostics(hass, entry)
    by_key = {c["key"]: c for c in data["containers"]}
    assert by_key["monitoring_grafana"]["active_job"] == {
        "id": "j1",
        "kind": "update_all",
        "state": "running",
        "percent": 88,
    }
    assert "active_job" not in by_key["media_jellyfin"]


async def test_nothing_private_in_the_output(hass, d2ha_server):
    """No token, no address, no Docker ids, no status text."""
    from custom_components.d2ha.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = await setup_integration(hass)
    blob = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    assert TOKEN not in blob
    assert URL not in blob
    assert "abc123" not in blob  # a Docker id
    assert "Up 3 days" not in blob  # the status text
