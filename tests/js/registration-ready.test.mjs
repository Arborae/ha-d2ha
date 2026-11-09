/**
 * Issue #266, the easy case: the frontend is already there when the module
 * loads (<home-assistant> defined), so the elements are defined at once in
 * the current registry.
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

const registry = fakeRegistry();
registry.define("home-assistant", class {});
globalThis.HTMLElement = class {};
globalThis.customElements = registry;
globalThis.window = { customElements: registry };

await import("../../custom_components/d2ha/frontend/d2ha-strategy.js");

test("elements are defined at once when the frontend is already there", () => {
  assert.ok(registry.get("ll-strategy-dashboard-d2ha"));
  assert.ok(registry.get("ll-strategy-view-d2ha"));
});
