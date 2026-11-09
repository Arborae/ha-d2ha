/**
 * D2HA dashboard strategy.
 *
 * Served by the ha-d2ha integration and registered in window.customStrategies,
 * so Settings → Dashboards → Add dashboard offers a D2HA page. The dashboard
 * config is rebuilt from the live entities every time the page opens, with
 * built-in cards only (sections, heading, tile, markdown).
 *
 * The generators are pure (hass in, config out) so they can be tested with
 * node:test; the browser-only registration at the bottom is skipped when
 * customElements is undefined.
 */
(function () {
  "use strict";

  var STRINGS = {
    en: {
      description:
        "Containers, updates and maintenance from D2HA, generated automatically.",
      overview: "Overview",
      running: "containers running",
      updates: "Updates",
      upToDate: "Everything is up to date.",
      unreachable: "D2HA is not reachable.",
      confirmUpdateAll:
        "Update all containers? They are updated one at a time, each with its own restart of a few seconds.",
      confirmCleanImages:
        "Delete the unused images? They can be downloaded again when needed.",
      maintenance: "Maintenance",
      other: "No stack",
    },
    it: {
      description:
        "Container, aggiornamenti e manutenzione da D2HA, generati automaticamente.",
      overview: "Panoramica",
      running: "container in esecuzione",
      updates: "Aggiornamenti",
      upToDate: "È tutto aggiornato.",
      unreachable: "D2HA non è raggiungibile.",
      confirmUpdateAll:
        "Aggiornare tutti i container? Vengono aggiornati uno alla volta, ognuno con un suo riavvio di qualche secondo.",
      confirmCleanImages:
        "Eliminare le immagini non usate? Si potranno riscaricare quando servono.",
      maintenance: "Manutenzione",
      other: "Senza stack",
    },
  };

  function strings(hass) {
    var language =
      (hass && hass.language) ||
      (typeof navigator !== "undefined" && navigator.language) ||
      "en";
    return language.toLowerCase().indexOf("it") === 0 ? STRINGS.it : STRINGS.en;
  }

  /** The D2HA server devices: a d2ha identifier, not behind another device. */
  function serverDevices(hass) {
    return Object.keys(hass.devices || {})
      .map(function (id) {
        return hass.devices[id];
      })
      .filter(function (device) {
        return (
          !device.via_device_id &&
          (device.identifiers || []).some(function (identifier) {
            return identifier[0] === "d2ha";
          })
        );
      });
  }

  /** The container devices hanging off one server (one per container, #245). */
  function containerDevices(hass, serverId) {
    return Object.keys(hass.devices || {})
      .map(function (id) {
        return hass.devices[id];
      })
      .filter(function (device) {
        return device.via_device_id === serverId;
      });
  }

  /** The entity ids of the d2ha platform living on one device. */
  function entitiesOf(hass, deviceId) {
    return Object.keys(hass.entities || {})
      .map(function (entityId) {
        return hass.entities[entityId];
      })
      .filter(function (entry) {
        return entry.device_id === deviceId && entry.platform === "d2ha";
      })
      .map(function (entry) {
        return entry.entity_id;
      });
  }

  function byTranslationKey(hass, entityIds, key) {
    return entityIds.filter(function (entityId) {
      var entry = hass.entities[entityId];
      return entry && entry.translation_key === key;
    });
  }

  function sortByName(hass, entityIds) {
    return entityIds.slice().sort(function (a, b) {
      var stateA = hass.states[a];
      var stateB = hass.states[b];
      var nameA = (stateA && stateA.attributes.friendly_name) || a;
      var nameB = (stateB && stateB.attributes.friendly_name) || b;
      return String(nameA).localeCompare(String(nameB));
    });
  }

  function tile(entityId, extra) {
    var card = { type: "tile", entity: entityId };
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        card[key] = extra[key];
      });
    }
    return card;
  }

  function buttonTile(entityId, confirmationText) {
    var action = {
      action: "perform-action",
      perform_action: "button.press",
      target: { entity_id: entityId },
    };
    if (confirmationText) {
      // A stray tap must not update every container or delete the images.
      action.confirmation = { text: confirmationText };
    }
    return tile(entityId, {
      name: { type: "entity" },
      hide_state: true, // an unpressed button reads "Unknown", like a fault
      tap_action: action,
    });
  }

  /** The view of one D2HA server device. */
  function generateView(hass, server, index) {
    var t = strings(hass);
    var serverEntityIds = entitiesOf(hass, server.id);
    var containers = containerDevices(hass, server.id);
    var sections = [];

    // With the entry not loaded every entity is unavailable: say once that
    // D2HA is not reachable, instead of a false "Everything is up to date.".
    // Any state but "unavailable" (buttons read "unknown") means D2HA has
    // answered; a disabled entity is simply not in hass.entities.
    var updatesAvailableIds = byTranslationKey(
      hass,
      serverEntityIds,
      "updates_available"
    );
    var reachable = serverEntityIds.some(function (entityId) {
      var state = hass.states[entityId];
      return state && state.state !== "unavailable";
    });

    // Overview: running out of the total, updates available.
    var overviewCards = [
      { type: "heading", heading: t.overview, icon: "mdi:docker" },
    ];
    if (!reachable) {
      overviewCards.push({ type: "markdown", content: t.unreachable });
    } else {
      byTranslationKey(hass, serverEntityIds, "containers_running").forEach(
        function (entityId) {
          var state = hass.states[entityId];
          var total =
            state && state.attributes.containers != null
              ? state.attributes.containers
              : "?";
          overviewCards.push({
            type: "markdown",
            content: "**" + state.state + " / " + total + "** " + t.running,
          });
        }
      );
    }
    updatesAvailableIds.forEach(function (entityId) {
      overviewCards.push(tile(entityId, { name: { type: "entity" } }));
    });
    sections.push({ type: "grid", cards: overviewCards });

    // Updates: a tile for each update that is on, then the two actions.
    var updateCards = [
      { type: "heading", heading: t.updates, icon: "mdi:update" },
    ];
    var pending = [];
    containers.forEach(function (device) {
      entitiesOf(hass, device.id).forEach(function (entityId) {
        var state = hass.states[entityId];
        if (
          state &&
          entityId.indexOf("update.") === 0 &&
          state.state === "on"
        ) {
          pending.push(entityId);
        }
      });
    });
    sortByName(hass, pending).forEach(function (entityId) {
      updateCards.push(
        tile(entityId, {
          name: { type: "device" },
          features: [{ type: "update-actions" }],
        })
      );
    });
    if (pending.length === 0 && reachable) {
      updateCards.push({ type: "markdown", content: t.upToDate });
    }
    ["update_all", "check_now"].forEach(function (key) {
      byTranslationKey(hass, serverEntityIds, key).forEach(function (entityId) {
        updateCards.push(
          buttonTile(entityId, key === "update_all" ? t.confirmUpdateAll : null)
        );
      });
    });
    sections.push({ type: "grid", cards: updateCards });

    // Containers: one section per stack (no-stack last), a tile per container.
    var byStack = {};
    var stackOrder = [];
    containers.forEach(function (device) {
      entitiesOf(hass, device.id).forEach(function (entityId) {
        var entry = hass.entities[entityId];
        var state = hass.states[entityId];
        if (!entry || !state || entry.translation_key !== "container_state") {
          return;
        }
        var stack = state.attributes.stack || "";
        if (!(stack in byStack)) {
          byStack[stack] = [];
          stackOrder.push(stack);
        }
        byStack[stack].push(entityId);
      });
    });
    stackOrder.sort(function (a, b) {
      if (a === "") {
        return 1;
      }
      if (b === "") {
        return -1;
      }
      return a.localeCompare(b);
    });
    stackOrder.forEach(function (stack) {
      var cards = [
        {
          type: "heading",
          heading: stack || t.other,
          icon: "mdi:cube-outline",
        },
      ];
      sortByName(hass, byStack[stack]).forEach(function (entityId) {
        var state = hass.states[entityId];
        var stateContent = ["state"];
        if (state.attributes.health) {
          stateContent.push("health");
        }
        stateContent.push("update_status");
        cards.push(
          tile(entityId, {
            name: { type: "device" },
            state_content: stateContent,
          })
        );
      });
      sections.push({ type: "grid", cards: cards });
    });

    // Maintenance: unused images and the cleanup button.
    var maintenanceCards = [
      { type: "heading", heading: t.maintenance, icon: "mdi:broom" },
    ];
    byTranslationKey(hass, serverEntityIds, "unused_images").forEach(
      function (entityId) {
        maintenanceCards.push(tile(entityId, { name: { type: "entity" } }));
      }
    );
    byTranslationKey(hass, serverEntityIds, "clean_images").forEach(
      function (entityId) {
        maintenanceCards.push(buttonTile(entityId, t.confirmCleanImages));
      }
    );
    sections.push({ type: "grid", cards: maintenanceCards });

    return {
      title: server.name || "D2HA",
      path: "d2ha" + (index ? "-" + index : ""),
      type: "sections",
      sections: sections,
    };
  }

  /** The whole dashboard: one view per D2HA server device. */
  function generateDashboard(hass) {
    var servers = serverDevices(hass);
    return {
      title: "D2HA",
      views: servers.map(function (server, index) {
        return generateView(hass, server, index);
      }),
    };
  }

  // For node:test: expose the pure generators without touching the DOM.
  if (typeof globalThis !== "undefined") {
    globalThis.__d2haStrategy = {
      generateDashboard: generateDashboard,
      generateView: generateView,
      serverDevices: serverDevices,
    };
  }

  if (typeof customElements === "undefined" || typeof window === "undefined") {
    return; // node:test or similar: nothing to register
  }

  var D2haDashboardStrategy = class extends HTMLElement {
    static async generate(config, hass) {
      return generateDashboard(hass);
    }
  };
  var D2haViewStrategy = class extends HTMLElement {
    static async generate(config, hass) {
      var servers = serverDevices(hass);
      var wanted = config && config.device_id;
      var server =
        servers.find(function (candidate) {
          return candidate.id === wanted;
        }) || servers[0];
      if (!server) {
        return {};
      }
      return generateView(hass, server, 0);
    }
  };

  // Home Assistant loads this module next to its own code, and its frontend
  // replaces window.customElements with a scoped registry when it starts: an
  // element defined before that is not in the new registry, and the dashboard
  // fails with "Timeout waiting for strategy element". So define the elements
  // only once the frontend is there (<home-assistant> defined), in the
  // registry window.customElements is by then.
  function register() {
    var registry = window.customElements;
    if (!registry.get("ll-strategy-dashboard-d2ha")) {
      registry.define("ll-strategy-dashboard-d2ha", D2haDashboardStrategy);
    }
    if (!registry.get("ll-strategy-view-d2ha")) {
      registry.define("ll-strategy-view-d2ha", D2haViewStrategy);
    }
  }
  (function waitForFrontend(tries) {
    if (window.customElements.get("home-assistant") || tries <= 0) {
      register();
    } else {
      setTimeout(function () {
        waitForFrontend(tries - 1);
      }, 50);
    }
  })(600); // up to 30 s, then register anyway

  var browserStrings = strings(null);
  window.customStrategies = window.customStrategies || [];
  if (
    !window.customStrategies.some(function (strategy) {
      return strategy.type === "d2ha";
    })
  ) {
    window.customStrategies.push({
      type: "d2ha",
      name: "D2HA",
      description: browserStrings.description,
      documentationURL: "https://github.com/Arborae/ha-d2ha",
      strategyType: "dashboard",
    });
  }
})();
