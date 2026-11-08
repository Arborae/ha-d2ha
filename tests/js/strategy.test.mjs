/**
 * The dashboard strategy generator, tested as a pure function:
 * sample hass.entities / hass.devices / hass.states in, dashboard config out.
 * Run with: node --test tests/js/
 */
import test from "node:test";
import assert from "node:assert/strict";

await import("../../custom_components/d2ha/frontend/d2ha-strategy.js");

const { generateDashboard } = globalThis.__d2haStrategy;

function sampleHass({ language = "en", jellyfinUpdate = "on", d2haDown = false } = {}) {
  const hass = {
    language,
    devices: {
      srv: {
        id: "srv",
        name: "D2HA",
        via_device_id: null,
        identifiers: [["d2ha", "entry1"]],
      },
      devJellyfin: {
        id: "devJellyfin",
        name: "jellyfin",
        via_device_id: "srv",
        identifiers: [["d2ha", "entry1_media_jellyfin"]],
      },
      devGrafana: {
        id: "devGrafana",
        name: "grafana",
        via_device_id: "srv",
        identifiers: [["d2ha", "entry1_monitoring_grafana"]],
      },
      other: {
        id: "other",
        name: "Unrelated device",
        via_device_id: null,
        identifiers: [["other_integration", "x"]],
      },
    },
    entities: {
      "sensor.d2ha_containers_running": {
        entity_id: "sensor.d2ha_containers_running",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "containers_running",
      },
      "sensor.d2ha_updates_available": {
        entity_id: "sensor.d2ha_updates_available",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "updates_available",
      },
      "sensor.d2ha_unused_images": {
        entity_id: "sensor.d2ha_unused_images",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "unused_images",
      },
      "button.d2ha_update_all": {
        entity_id: "button.d2ha_update_all",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "update_all",
      },
      "button.d2ha_check_for_updates": {
        entity_id: "button.d2ha_check_for_updates",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "check_now",
      },
      "button.d2ha_clean_images": {
        entity_id: "button.d2ha_clean_images",
        device_id: "srv",
        platform: "d2ha",
        translation_key: "clean_images",
      },
      "update.jellyfin_update": {
        entity_id: "update.jellyfin_update",
        device_id: "devJellyfin",
        platform: "d2ha",
        translation_key: "container_update",
      },
      "sensor.jellyfin_state": {
        entity_id: "sensor.jellyfin_state",
        device_id: "devJellyfin",
        platform: "d2ha",
        translation_key: "container_state",
      },
      "update.grafana_update": {
        entity_id: "update.grafana_update",
        device_id: "devGrafana",
        platform: "d2ha",
        translation_key: "container_update",
      },
      "sensor.grafana_state": {
        entity_id: "sensor.grafana_state",
        device_id: "devGrafana",
        platform: "d2ha",
        translation_key: "container_state",
      },
      "sensor.unrelated": {
        entity_id: "sensor.unrelated",
        device_id: "other",
        platform: "other_integration",
      },
    },
    states: {
      "sensor.d2ha_containers_running": {
        state: "2",
        attributes: { containers: 3, friendly_name: "Containers running" },
      },
      "sensor.d2ha_updates_available": {
        state: "1",
        attributes: { friendly_name: "Updates available" },
      },
      "sensor.d2ha_unused_images": {
        state: "4",
        attributes: { friendly_name: "Unused images" },
      },
      "button.d2ha_update_all": {
        state: "unknown",
        attributes: { friendly_name: "Update all" },
      },
      "button.d2ha_check_for_updates": {
        state: "unknown",
        attributes: { friendly_name: "Check for updates" },
      },
      "button.d2ha_clean_images": {
        state: "unknown",
        attributes: { friendly_name: "Clean images" },
      },
      "update.jellyfin_update": {
        state: jellyfinUpdate,
        attributes: { friendly_name: "jellyfin Update" },
      },
      "sensor.jellyfin_state": {
        state: "running",
        attributes: {
          friendly_name: "jellyfin State",
          stack: "media",
          health: "healthy",
          update_status: "available",
        },
      },
      "update.grafana_update": {
        state: "off",
        attributes: { friendly_name: "grafana Update" },
      },
      "sensor.grafana_state": {
        state: "running",
        attributes: {
          friendly_name: "grafana State",
          stack: "monitoring",
          health: "",
          update_status: "current",
        },
      },
      "sensor.unrelated": { state: "x", attributes: {} },
    },
  };
  if (d2haDown) {
    // The entry is not loaded: every d2ha entity is unavailable.
    for (const [entityId, entry] of Object.entries(hass.entities)) {
      if (entry.platform === "d2ha" && hass.states[entityId]) {
        hass.states[entityId] = {
          state: "unavailable",
          attributes: hass.states[entityId].attributes,
        };
      }
    }
  }
  return hass;
}

/** The sections of a view, keyed by the text of their heading card. */
function sectionsByHeading(view) {
  const map = {};
  for (const section of view.sections) {
    const heading = section.cards[0];
    assert.equal(heading.type, "heading");
    map[heading.heading] = section.cards.slice(1);
  }
  return map;
}

test("one view per server device, counters in the overview", () => {
  const dashboard = generateDashboard(sampleHass());
  assert.equal(dashboard.title, "D2HA");
  assert.equal(dashboard.views.length, 1);
  const view = dashboard.views[0];
  assert.equal(view.title, "D2HA");
  assert.equal(view.type, "sections");
  const sections = sectionsByHeading(view);
  const overview = sections["Overview"];
  assert.ok(
    overview.some((card) => card.type === "markdown" && card.content.includes("2 / 3")),
    "running out of the total"
  );
  assert.ok(overview.some((card) => card.entity === "sensor.d2ha_updates_available"));
});

test("updates: only pending ones, with actions, then the two buttons", () => {
  const sections = sectionsByHeading(generateDashboard(sampleHass()).views[0]);
  const updates = sections["Updates"];
  assert.deepEqual(
    updates.map((card) => card.entity),
    ["update.jellyfin_update", "button.d2ha_update_all", "button.d2ha_check_for_updates"]
  );
  const updateTile = updates.find((card) => card.entity === "update.jellyfin_update");
  assert.deepEqual(updateTile.features, [{ type: "update-actions" }]);
  const updateAll = updates.find((card) => card.entity === "button.d2ha_update_all");
  assert.equal(updateAll.tap_action.action, "perform-action");
  assert.equal(updateAll.tap_action.perform_action, "button.press");
  assert.ok(!updates.some((card) => card.type === "markdown"));
});

test("no pending updates: the up-to-date note instead of tiles", () => {
  const sections = sectionsByHeading(
    generateDashboard(sampleHass({ jellyfinUpdate: "off" })).views[0]
  );
  const updates = sections["Updates"];
  assert.ok(
    updates.some(
      (card) => card.type === "markdown" && card.content === "Everything is up to date."
    )
  );
  assert.ok(!updates.some((card) => card.entity === "update.jellyfin_update"));
});

test("d2ha unreachable: one note, no up-to-date note, no counter", () => {
  const sections = sectionsByHeading(
    generateDashboard(sampleHass({ d2haDown: true })).views[0]
  );
  const overview = sections["Overview"];
  assert.ok(
    overview.some(
      (card) => card.type === "markdown" && card.content === "D2HA is not reachable."
    ),
    "the unreachable note"
  );
  assert.ok(
    !overview.some(
      (card) => card.type === "markdown" && card.content.includes("containers running")
    ),
    "no unavailable / ? counter"
  );
  const updates = sections["Updates"];
  assert.ok(
    !updates.some((card) => card.type === "markdown"),
    "no false up-to-date note"
  );
});

test("d2ha unreachable, in Italian", () => {
  const sections = sectionsByHeading(
    generateDashboard(sampleHass({ d2haDown: true, language: "it" })).views[0]
  );
  assert.ok(
    sections["Panoramica"].some(
      (card) => card.type === "markdown" && card.content === "D2HA non è raggiungibile."
    )
  );
  assert.ok(!sections["Aggiornamenti"].some((card) => card.type === "markdown"));
});

test("update all and clean images ask for confirmation, check does not", () => {
  const sections = sectionsByHeading(generateDashboard(sampleHass()).views[0]);
  const updateAll = sections["Updates"].find(
    (card) => card.entity === "button.d2ha_update_all"
  );
  assert.equal(typeof updateAll.tap_action.confirmation.text, "string");
  assert.ok(updateAll.tap_action.confirmation.text.length > 0);
  const checkNow = sections["Updates"].find(
    (card) => card.entity === "button.d2ha_check_for_updates"
  );
  assert.equal(checkNow.tap_action.confirmation, undefined);
  const cleanImages = sections["Maintenance"].find(
    (card) => card.entity === "button.d2ha_clean_images"
  );
  assert.equal(typeof cleanImages.tap_action.confirmation.text, "string");
  assert.ok(cleanImages.tap_action.confirmation.text.length > 0);
});

test("containers grouped by stack, health and update status visible", () => {
  const sections = sectionsByHeading(generateDashboard(sampleHass()).views[0]);
  const media = sections["media"];
  assert.deepEqual(
    media.map((card) => card.entity),
    ["sensor.jellyfin_state"]
  );
  assert.deepEqual(media[0].state_content, ["state", "health", "update_status"]);
  const monitoring = sections["monitoring"];
  assert.deepEqual(
    monitoring.map((card) => card.entity),
    ["sensor.grafana_state"]
  );
  assert.deepEqual(monitoring[0].state_content, ["state", "update_status"]);
});

test("maintenance: unused images and the cleanup button", () => {
  const sections = sectionsByHeading(generateDashboard(sampleHass()).views[0]);
  const maintenance = sections["Maintenance"];
  assert.deepEqual(
    maintenance.map((card) => card.entity),
    ["sensor.d2ha_unused_images", "button.d2ha_clean_images"]
  );
});

test("italian labels when Home Assistant is in Italian", () => {
  const sections = sectionsByHeading(
    generateDashboard(sampleHass({ language: "it" })).views[0]
  );
  assert.ok(sections["Panoramica"]);
  assert.ok(sections["Aggiornamenti"]);
  assert.ok(sections["Manutenzione"]);
});

test("two D2HA servers: one view each", () => {
  const hass = sampleHass();
  hass.devices.srv2 = {
    id: "srv2",
    name: "D2HA ufficio",
    via_device_id: null,
    identifiers: [["d2ha", "entry2"]],
  };
  const dashboard = generateDashboard(hass);
  assert.equal(dashboard.views.length, 2);
  assert.equal(dashboard.views[1].title, "D2HA ufficio");
  assert.equal(dashboard.views[1].path, "d2ha-1");
});

test("devices and entities of other integrations are ignored", () => {
  const view = generateDashboard(sampleHass()).views[0];
  assert.ok(!JSON.stringify(view).includes("sensor.unrelated"));
});
