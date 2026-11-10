"""The device of a container D2HA no longer lists is removed after a day."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
import pytest

from homeassistant.helpers import device_registry as dr

from conftest import CONTAINERS, URL, register_d2ha, setup_integration

pytestmark = pytest.mark.asyncio

WITHOUT_JELLYFIN = {
    **CONTAINERS,
    "containers": [c for c in CONTAINERS["containers"] if c["key"] != "media_jellyfin"],
}


def device(hass, entry, key=None):
    """The device of a container, or the server device without a key."""
    identifier = f"{entry.entry_id}_{key}" if key else entry.entry_id
    return dr.async_get(hass).async_get_device_by_identifier(
        ("d2ha", identifier), entry.entry_id
    )


async def answer(hass, entry, d2ha_server, freezer, containers=CONTAINERS, after=None):
    """Let time pass, then one poll with D2HA giving this list of containers."""
    if after:
        freezer.tick(after)
    d2ha_server.clear_requests()
    register_d2ha(d2ha_server, containers=containers)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def no_answer(hass, entry, d2ha_server, freezer, after=None):
    """Let time pass, then one poll with D2HA unreachable."""
    if after:
        freezer.tick(after)
    d2ha_server.clear_requests()
    d2ha_server.get(f"{URL}/api/v1/info", exc=aiohttp.ClientConnectionError("refused"))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_a_gone_container_loses_its_device_after_a_day(
    hass, d2ha_server, freezer, caplog
):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    assert device(hass, entry, "media_jellyfin") is not None
    assert hass.states.get("update.jellyfin_update").state == "unavailable"
    with caplog.at_level(logging.INFO, logger="custom_components.d2ha"):
        await answer(
            hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=1)
        )
    assert device(hass, entry, "media_jellyfin") is None
    assert hass.states.get("update.jellyfin_update") is None
    assert hass.states.get("sensor.jellyfin_state") is None
    assert "Removing the device of jellyfin" in caplog.text
    # The server and the containers that are there stay.
    assert device(hass, entry) is not None
    assert device(hass, entry, "monitoring_grafana") is not None
    assert hass.states.get("sensor.grafana_state").state == "running"


async def test_the_time_d2ha_does_not_answer_is_not_absence(hass, d2ha_server, freezer):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    await no_answer(hass, entry, d2ha_server, freezer, after=timedelta(minutes=1))
    await no_answer(hass, entry, d2ha_server, freezer, after=timedelta(hours=30))
    assert device(hass, entry, "media_jellyfin") is not None
    # D2HA is back, still without jellyfin: the day is counted from its answers.
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(minutes=1)
    )
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    assert device(hass, entry, "media_jellyfin") is not None
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=1)
    )
    assert device(hass, entry, "media_jellyfin") is None


async def test_an_empty_list_removes_nothing(hass, d2ha_server, freezer):
    entry = await setup_integration(hass)
    empty = {**CONTAINERS, "containers": []}
    await answer(hass, entry, d2ha_server, freezer, empty)
    await answer(hass, entry, d2ha_server, freezer, empty, after=timedelta(hours=25))
    await answer(hass, entry, d2ha_server, freezer, empty, after=timedelta(hours=25))
    for key in ("media_jellyfin", "monitoring_grafana", "db"):
        assert device(hass, entry, key) is not None


async def test_a_container_that_is_back_starts_the_count_again(
    hass, d2ha_server, freezer
):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    await answer(hass, entry, d2ha_server, freezer, after=timedelta(minutes=1))
    assert hass.states.get("sensor.jellyfin_state").state == "running"
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(minutes=1)
    )
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    assert device(hass, entry, "media_jellyfin") is not None
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=1)
    )
    assert device(hass, entry, "media_jellyfin") is None


async def test_a_restart_starts_the_count_again(hass, d2ha_server, freezer):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    # Home Assistant restarts: the device is in the registry, the container is not there.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=23)
    )
    assert device(hass, entry, "media_jellyfin") is not None
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=1)
    )
    assert device(hass, entry, "media_jellyfin") is None


async def test_a_container_back_after_the_removal_gets_new_entities(
    hass, d2ha_server, freezer
):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    await answer(
        hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN, after=timedelta(hours=24)
    )
    assert device(hass, entry, "media_jellyfin") is None
    await answer(hass, entry, d2ha_server, freezer, after=timedelta(minutes=1))
    assert device(hass, entry, "media_jellyfin") is not None
    assert hass.states.get("update.jellyfin_update").state == "on"
    assert hass.states.get("sensor.jellyfin_state").state == "running"
    # Once only: the next poll adds nothing more.
    await answer(hass, entry, d2ha_server, freezer, after=timedelta(minutes=1))
    assert len(dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)) == 4


async def test_a_device_deleted_by_hand_comes_back_with_its_container(
    hass, d2ha_server, freezer
):
    entry = await setup_integration(hass)
    await answer(hass, entry, d2ha_server, freezer, WITHOUT_JELLYFIN)
    # What Home Assistant does for Delete on the device page.
    dr.async_get(hass).async_remove_device(device(hass, entry, "media_jellyfin").id)
    await hass.async_block_till_done()
    assert hass.states.get("update.jellyfin_update") is None
    await answer(hass, entry, d2ha_server, freezer, after=timedelta(minutes=1))
    assert hass.states.get("update.jellyfin_update").state == "on"
    assert hass.states.get("sensor.jellyfin_state").state == "running"
