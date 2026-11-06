"""Entities reflect what D2HA exposes: counters, states, updates, buttons."""

from __future__ import annotations

import asyncio

import pytest

from homeassistant.exceptions import HomeAssistantError

from conftest import (
    INFO,
    URL,
    make_container,
    register_d2ha,
    setup_integration,
    with_container,
)

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


async def test_state_sensor_name_mentions_the_container(hass, d2ha_server):
    await setup_integration(hass)
    grafana = hass.states.get("sensor.d2ha_grafana_state")
    assert "grafana state" in grafana.attributes["friendly_name"]


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


async def test_unknown_update_has_no_latest_version(hass, d2ha_server):
    """D2HA does not know: HA must show "unknown", not "up-to-date"."""
    weird = make_container(
        "weird",
        "weird",
        update="unknown",
        installed_version="1.0",
        latest_version=None,
    )
    d2ha_server.clear_requests()
    register_d2ha(d2ha_server, containers=with_container(weird))
    await setup_integration(hass)
    state = hass.states.get("update.d2ha_weird")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["latest_version"] is None


async def test_proxy_has_update_but_no_install(hass, d2ha_server):
    """The socket proxy can show an update, but D2HA must not touch it."""
    proxy = make_container(
        "docker_proxy",
        "docker-proxy",
        is_proxy=True,
        can_update=False,
        update="available",
        installed_version="1.0",
        latest_version="1.1",
    )
    d2ha_server.clear_requests()
    register_d2ha(d2ha_server, containers=with_container(proxy))
    await setup_integration(hass)
    state = hass.states.get("update.d2ha_docker_proxy")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["supported_features"] & 1 == 0  # no INSTALL


async def test_update_all_progress_follows_the_label(hass, d2ha_server):
    """An update-all job updates one container at a time: label says which."""
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
    await setup_integration(hass)
    grafana = hass.states.get("update.d2ha_grafana")
    assert grafana.attributes["in_progress"] is True
    assert grafana.attributes["update_percentage"] == 88
    jellyfin = hass.states.get("update.d2ha_jellyfin")
    assert jellyfin.attributes["in_progress"] is False
    assert jellyfin.attributes["update_percentage"] is None


async def test_new_containers_get_entities_after_setup(hass, d2ha_server):
    """A container enabled in D2HA later appears without a reload."""
    entry = await setup_integration(hass)
    assert hass.states.get("update.d2ha_radarr") is None
    radarr = make_container(
        "media_radarr",
        "radarr",
        update="available",
        can_update=True,
        installed_version="5.0",
        latest_version="5.1",
    )
    d2ha_server.clear_requests()
    register_d2ha(d2ha_server, containers=with_container(radarr))
    await entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("update.d2ha_radarr") is not None
    assert hass.states.get("sensor.d2ha_radarr_state") is not None


async def test_buttons(hass, d2ha_server):
    await setup_integration(hass)
    assert hass.states.get("button.d2ha_check_for_updates") is not None
    assert hass.states.get("button.d2ha_update_all") is not None
    assert hass.states.get("button.d2ha_clean_images") is not None


async def test_read_only_hides_the_write_buttons(hass, d2ha_server):
    d2ha_server.clear_requests()
    register_d2ha(d2ha_server, info={**INFO, "read_only": True})
    await setup_integration(hass)
    assert hass.states.get("button.d2ha_check_for_updates") is not None
    assert hass.states.get("button.d2ha_update_all") is None
    assert hass.states.get("button.d2ha_clean_images") is None


async def test_update_all_with_nothing_to_update_is_not_an_error(hass, d2ha_server):
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/update-all",
        status=409,
        json={"error": "nothing_to_update"},
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.d2ha_update_all"},
        blocking=True,
    )


async def test_install_calls_update_and_follows_the_job(hass, d2ha_server):
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        json={"id": "job1", "state": "running"},
    )
    d2ha_server.get(
        f"{URL}/api/v1/jobs/job1",
        json={"id": "job1", "state": "done", "result": {"changed": True}},
    )
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.d2ha_jellyfin"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.d2ha_jellyfin")
    assert state.attributes["in_progress"] is False


async def test_install_refused_when_can_update_is_false(hass, d2ha_server):
    await setup_integration(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.d2ha_db"},
            blocking=True,
        )


async def test_install_error_is_translated(hass, d2ha_server):
    """A known API error code becomes a translated message."""
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=403,
        json={"error": "read_only"},
    )
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.d2ha_jellyfin"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "api_read_only"


async def test_progress_is_live_during_install(hass, d2ha_server, monkeypatch):
    """While the job runs, the entity shows its percentage as it changes."""
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMockResponse,
    )

    from custom_components.d2ha import update as update_module

    monkeypatch.setattr(update_module, "JOB_POLL_INTERVAL", 0.01)
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        json={"id": "job1", "state": "queued"},
    )
    polls = [{"id": "job1", "state": "running", "percent": 40}] * 5

    async def job_progress(method, url, data):
        payload = (
            polls.pop(0) if polls else {"id": "job1", "state": "done", "percent": 100}
        )
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    d2ha_server.get(f"{URL}/api/v1/jobs/job1", side_effect=job_progress)
    task = hass.async_create_task(
        hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.d2ha_jellyfin"},
            blocking=True,
        )
    )
    seen = False
    for _ in range(200):
        await asyncio.sleep(0.01)
        state = hass.states.get("update.d2ha_jellyfin")
        if state is not None and state.attributes.get("update_percentage") == 40:
            seen = True
            break
    await task
    assert seen, "the percentage never showed while the job was running"
    state = hass.states.get("update.d2ha_jellyfin")
    assert state.attributes["in_progress"] is False
