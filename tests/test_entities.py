"""Entities reflect what D2HA exposes: counters, states, updates, buttons."""

from __future__ import annotations

import asyncio

import pytest

from homeassistant.exceptions import HomeAssistantError

from conftest import (
    CONTAINERS,
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
    jellyfin = hass.states.get("sensor.jellyfin_state")
    assert jellyfin.state == "running"
    assert jellyfin.attributes["image"] == "jellyfin/jellyfin:latest"
    assert jellyfin.attributes["update_status"] == "available"
    assert hass.states.get("sensor.db_state").state == "exited"


async def test_state_sensor_sits_under_the_container_device(hass, d2ha_server):
    """The device names the container; the entity is just "State"."""
    await setup_integration(hass)
    grafana = hass.states.get("sensor.grafana_state")
    assert grafana.attributes["friendly_name"] == "grafana State"


async def test_one_device_per_container(hass, d2ha_server):
    """Update and state of a container live on its own device, under D2HA."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    from custom_components.d2ha.const import DOMAIN

    entry = await setup_integration(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    server = devices.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert server is not None
    assert server.name == "D2HA"
    for key, name in (
        ("media_jellyfin", "jellyfin"),
        ("monitoring_grafana", "grafana"),
        ("db", "db"),
    ):
        device = devices.async_get_device_by_identifier(
            (DOMAIN, f"{entry.entry_id}_{key}"), entry.entry_id
        )
        assert device is not None, key
        assert device.name == name
        assert device.via_device_id == server.id
    jellyfin = devices.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_media_jellyfin"), entry.entry_id
    )
    assert entities.async_get("update.jellyfin_update").device_id == jellyfin.id
    assert entities.async_get("sensor.jellyfin_state").device_id == jellyfin.id
    # Counters and buttons stay on the server device.
    assert entities.async_get("sensor.d2ha_updates_available").device_id == server.id
    assert entities.async_get("button.d2ha_update_all").device_id == server.id


async def test_update_title_is_the_image_without_tag(hass, d2ha_server):
    """Settings → Updates shows area · title · latest version on the second line."""
    await setup_integration(hass)
    jellyfin = hass.states.get("update.jellyfin_update")
    assert jellyfin.attributes["title"] == "jellyfin/jellyfin"
    db = hass.states.get("update.db_update")
    assert db.attributes["title"] == "postgres"


async def test_update_title_handles_digests_and_registry_ports(hass, d2ha_server):
    from custom_components.d2ha.update import _image_name

    assert _image_name("img@sha256:abc123") == "img"
    assert _image_name("registry:5000/team/app:1.2") == "registry:5000/team/app"
    assert _image_name("team/app") == "team/app"
    assert _image_name("") is None
    assert _image_name(None) is None


async def test_stale_container_devices_can_be_deleted(hass, d2ha_server):
    """HA may delete a container device only once D2HA no longer lists it."""
    from homeassistant.helpers import device_registry as dr

    from custom_components.d2ha import async_remove_config_entry_device
    from custom_components.d2ha.const import DOMAIN

    entry = await setup_integration(hass)
    devices = dr.async_get(hass)
    server = devices.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    jellyfin = devices.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_media_jellyfin"), entry.entry_id
    )
    assert not await async_remove_config_entry_device(hass, entry, server)
    assert not await async_remove_config_entry_device(hass, entry, jellyfin)
    # jellyfin disappears from D2HA (disabled there, or removed from Docker).
    d2ha_server.clear_requests()
    register_d2ha(
        d2ha_server,
        containers={
            **CONTAINERS,
            "containers": [
                c for c in CONTAINERS["containers"] if c["key"] != "media_jellyfin"
            ],
        },
    )
    await entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()
    assert await async_remove_config_entry_device(hass, entry, jellyfin)
    assert not await async_remove_config_entry_device(hass, entry, server)


async def test_no_device_is_deleted_while_d2ha_is_unreachable(hass, d2ha_server):
    """With D2HA down at start-up the entry is not loaded: keep every device."""
    import aiohttp

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import device_registry as dr

    from custom_components.d2ha import async_remove_config_entry_device
    from custom_components.d2ha.const import DOMAIN

    d2ha_server.clear_requests()
    d2ha_server.get(f"{URL}/api/v1/info", exc=aiohttp.ClientConnectionError("refused"))
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    # A container device left from the last run.
    jellyfin = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_media_jellyfin")},
    )
    assert not await async_remove_config_entry_device(hass, entry, jellyfin)


async def test_update_entities(hass, d2ha_server):
    await setup_integration(hass)
    jellyfin = hass.states.get("update.jellyfin_update")
    assert jellyfin is not None
    assert jellyfin.state == "on"  # an update is available
    assert jellyfin.attributes["installed_version"] == "12.3"
    assert jellyfin.attributes["latest_version"] == "12.4"
    assert (
        jellyfin.attributes["release_url"]
        == "https://github.com/jellyfin/jellyfin/releases/tag/v12.4"
    )
    grafana = hass.states.get("update.grafana_update")
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
    state = hass.states.get("update.weird_update")
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
    state = hass.states.get("update.docker_proxy_update")
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
    grafana = hass.states.get("update.grafana_update")
    assert grafana.attributes["in_progress"] is True
    assert grafana.attributes["update_percentage"] == 88
    jellyfin = hass.states.get("update.jellyfin_update")
    assert jellyfin.attributes["in_progress"] is False
    assert jellyfin.attributes["update_percentage"] is None


async def test_new_containers_get_entities_after_setup(hass, d2ha_server):
    """A container enabled in D2HA later appears without a reload."""
    entry = await setup_integration(hass)
    assert hass.states.get("update.radarr_update") is None
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
    assert hass.states.get("update.radarr_update") is not None
    assert hass.states.get("sensor.radarr_state") is not None


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
        {"entity_id": "update.jellyfin_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.jellyfin_update")
    assert state.attributes["in_progress"] is False


async def test_install_refused_when_can_update_is_false(hass, d2ha_server):
    await setup_integration(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.db_update"},
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
            {"entity_id": "update.jellyfin_update"},
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
            {"entity_id": "update.jellyfin_update"},
            blocking=True,
        )
    )
    seen = False
    for _ in range(200):
        await asyncio.sleep(0.01)
        state = hass.states.get("update.jellyfin_update")
        if state is not None and state.attributes.get("update_percentage") == 40:
            seen = True
            break
    await task
    assert seen, "the percentage never showed while the job was running"
    state = hass.states.get("update.jellyfin_update")
    assert state.attributes["in_progress"] is False


async def test_failed_job_without_error_uses_the_generic_message(hass, d2ha_server):
    """D2HA may send "error": null on a failed job; the message stays generic."""
    await setup_integration(hass)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        json={"id": "job1", "state": "queued"},
    )
    d2ha_server.get(
        f"{URL}/api/v1/jobs/job1",
        json={"id": "job1", "state": "failed", "error": None},
    )
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.jellyfin_update"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "update_failed"
    assert excinfo.value.translation_placeholders == {"error": "error.generic"}


async def test_the_new_version_shows_right_after_the_install(hass, d2ha_server, monkeypatch):
    """No stale state: the refresh at the end of the job is not debounced."""
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMockResponse,
    )

    from custom_components.d2ha import update as update_module

    monkeypatch.setattr(update_module, "JOB_POLL_INTERVAL", 0.01)
    await setup_integration(hass)
    updated = {
        **CONTAINERS,
        "containers": [
            {
                **c,
                "update": "current",
                "installed_version": "12.4",
                "latest_version": "12.4",
            }
            if c["key"] == "media_jellyfin"
            else c
            for c in CONTAINERS["containers"]
        ],
    }
    containers_calls = 0

    async def containers_side_effect(method, url, data):
        # Old data at the refresh right after the job starts, new data at the end.
        nonlocal containers_calls
        containers_calls += 1
        payload = CONTAINERS if containers_calls == 1 else updated
        return AiohttpClientMockResponse(method=method, url=url, json=payload)

    d2ha_server.clear_requests()
    d2ha_server.get(f"{URL}/api/v1/info", json=INFO)
    d2ha_server.get(f"{URL}/api/v1/jobs", json={"jobs": []})
    d2ha_server.get(f"{URL}/api/v1/containers?ha=1", side_effect=containers_side_effect)
    d2ha_server.post(
        f"{URL}/api/v1/containers/media_jellyfin/update",
        status=202,
        json={"id": "job1", "state": "queued"},
    )
    d2ha_server.get(
        f"{URL}/api/v1/jobs/job1",
        json={"id": "job1", "state": "done", "result": {"changed": True}},
    )
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.jellyfin_update"},
        blocking=True,
    )
    state = hass.states.get("update.jellyfin_update")
    assert state.attributes["installed_version"] == "12.4"
    assert state.state == "off"


async def test_unused_images_is_diagnostic_the_rest_is_primary(hass, d2ha_server):
    """Housekeeping under "Diagnostic"; counters and buttons stay primary."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity import EntityCategory

    await setup_integration(hass)
    entities = er.async_get(hass)
    assert (
        entities.async_get("sensor.d2ha_unused_images").entity_category
        is EntityCategory.DIAGNOSTIC
    )
    for entity_id in (
        "sensor.d2ha_updates_available",
        "sensor.d2ha_containers_running",
        "sensor.jellyfin_state",
        "button.d2ha_check_for_updates",
        "button.d2ha_update_all",
        "button.d2ha_clean_images",
    ):
        assert entities.async_get(entity_id).entity_category is None, entity_id


async def test_icons_json_matches_the_translation_keys():
    """No typos between the entities and icons.json (hassfest checks the rest)."""
    import json
    from pathlib import Path

    icons = json.loads(
        (
            Path(__file__).parent.parent / "custom_components/d2ha/icons.json"
        ).read_text()
    )
    assert set(icons["entity"]["sensor"]) == {
        "updates_available",
        "containers_running",
        "unused_images",
        "container_state",
    }
    assert set(icons["entity"]["button"]) == {
        "check_now",
        "update_all",
        "clean_images",
    }
    # Every Docker state of API.md has its own icon.
    assert set(icons["entity"]["sensor"]["container_state"]["state"]) == {
        "created",
        "restarting",
        "running",
        "paused",
        "exited",
        "dead",
    }
