"""Entities reflect what D2HA exposes: counters, states, update entities."""

from __future__ import annotations

import pytest


from conftest import URL, setup_integration

pytestmark = pytest.mark.asyncio


async def test_counters(hass, d2ha_server):
    await setup_integration(hass)
    assert hass.states.get("sensor.d2ha_updates_available").state == "1"
    running = hass.states.get("sensor.d2ha_containers_running")
    assert running.state == "2"
    assert running.attributes["containers"] == 3
    assert hass.states.get("sensor.d2ha_unused_images").state == "4"


async def test_container_states(hass, d2ha_server):
    await setup_integration(hass)
    jellyfin = hass.states.get("sensor.d2ha_jellyfin_state")
    assert jellyfin.state == "running"
    assert jellyfin.attributes["image"] == "jellyfin/jellyfin:latest"
    assert jellyfin.attributes["update_status"] == "available"
    assert hass.states.get("sensor.d2ha_db_state").state == "exited"


async def test_update_entities(hass, d2ha_server):
    await setup_integration(hass)
    jellyfin = hass.states.get("update.d2ha_jellyfin")
    assert jellyfin is not None
    assert jellyfin.state == "on"  # an update is available
    assert jellyfin.attributes["installed_version"] == "12.3"
    assert jellyfin.attributes["latest_version"] == "12.4"
    assert (
        jellyfin.attributes["release_url"]
        == "https://github.com/jellyfin/jellyfin/releases/tag/v12.4"
    )
    grafana = hass.states.get("update.d2ha_grafana")
    assert grafana.state == "off"  # already current
    assert grafana.attributes["latest_version"] == "13.3.0"


async def test_buttons(hass, d2ha_server):
    await setup_integration(hass)
    assert hass.states.get("button.d2ha_check_for_updates") is not None
    assert hass.states.get("button.d2ha_update_all") is not None
    assert hass.states.get("button.d2ha_clean_images") is not None


async def test_read_only_hides_the_write_buttons(hass, d2ha_server):
    from conftest import INFO

    d2ha_server.clear()
    d2ha_server.get(f"{URL}/api/v1/info", payload={**INFO, "read_only": True})
    from conftest import CONTAINERS

    d2ha_server.get(f"{URL}/api/v1/containers?ha=1", payload=CONTAINERS)
    d2ha_server.get(f"{URL}/api/v1/jobs", payload={"jobs": []})
    await setup_integration(hass)
    assert hass.states.get("button.d2ha_check_for_updates") is not None
    assert hass.states.get("button.d2ha_update_all") is None
    assert hass.states.get("button.d2ha_clean_images") is None


async def test_install_calls_update_and_follows_the_job(hass, d2ha_server):
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        payload={"id": "job1", "state": "running"},
    )
    d2ha_server.get(
        f"{URL}/api/v1/jobs/job1",
        payload={"id": "job1", "state": "done", "result": {"changed": True}},
    )
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.d2ha_jellyfin"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_install_refused_when_can_update_is_false(hass, d2ha_server):
    from homeassistant.exceptions import HomeAssistantError

    await setup_integration(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.d2ha_db"},
            blocking=True,
        )
