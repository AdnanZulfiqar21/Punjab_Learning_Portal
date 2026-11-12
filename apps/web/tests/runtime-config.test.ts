// ROLE-EXPLICIT-01: a production build must be told its role; nothing else changes.
import assert from "node:assert/strict";
import { test } from "node:test";
import { readRuntimeConfig, requireExplicitRole, WebConfigurationError } from "../src/lib/runtime-config.ts";

test("a production build refuses to start without a role, or with a misspelt one", () => {
  assert.throws(() => requireExplicitRole({ NODE_ENV: "production" }), WebConfigurationError);
  assert.throws(() => requireExplicitRole({ NODE_ENV: "production", PORTAL_ROLE: "" }), WebConfigurationError);
  assert.throws(() => requireExplicitRole({ NODE_ENV: "production", PORTAL_ROLE: "prodution" }), /not a known role/);
});

test("a named role, the development server and the build step are accepted", () => {
  for (const role of ["development", "test", "staging", "production"]) {
    assert.doesNotThrow(() => requireExplicitRole({ NODE_ENV: "production", PORTAL_ROLE: role }));
  }
  assert.doesNotThrow(() => requireExplicitRole({ NODE_ENV: "development" }));
  assert.doesNotThrow(() => requireExplicitRole({ NODE_ENV: "production", NEXT_PHASE: "phase-production-build" }));
});

test("a deployed role still needs a real API address", () => {
  assert.throws(() => readRuntimeConfig({ PORTAL_ROLE: "production" }), /PORTAL_API_INTERNAL_ORIGIN is required/);
  assert.equal(readRuntimeConfig({ PORTAL_ROLE: "development" }).apiOrigin, "http://127.0.0.1:8100");
});
