/**
 * Issue #266: Home Assistant replaces window.customElements with its scoped
 * registry when the frontend starts. The module must define the strategy
 * elements in whatever registry window.customElements is once <home-assistant>
 * is defined — not in the registry that was current when the module loaded.
 * Run with: node --test tests/js/
 */
import test from "node:test";
import assert from "node:assert/strict";

function fakeRegistry() {
  const elements = new Map();
  return {
    get: (name) => elements.get(name),
    define: (name, ctor) => elements.set(name, ctor),
  };
}

// The module loads next to HA's own bundles, before the frontend starts.
const oldRegistry = fakeRegistry();
globalThis.HTMLElement = class {};
globalThis.customElements = oldRegistry;
globalThis.window = { customElements: oldRegistry };

await import("../../custom_components/d2ha/frontend/d2ha-strategy.js");

test("no element is defined before the frontend is there", () => {
  assert.equal(oldRegistry.get("ll-strategy-dashboard-d2ha"), undefined);
  assert.equal(oldRegistry.get("ll-strategy-view-d2ha"), undefined);
});

test("elements land in the new registry after the swap", async () => {
  // HA starts: window.customElements becomes the scoped registry.
  const scoped = fakeRegistry();
  globalThis.window.customElements = scoped;
  globalThis.customElements = scoped;
  scoped.define("home-assistant", class {});
  // The module polls every 50 ms; give it a few rounds.
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.ok(scoped.get("ll-strategy-dashboard-d2ha"));
  assert.ok(scoped.get("ll-strategy-view-d2ha"));
  assert.equal(oldRegistry.get("ll-strategy-dashboard-d2ha"), undefined);
});
