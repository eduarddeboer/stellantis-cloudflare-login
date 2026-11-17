import test from "node:test";
import assert from "node:assert/strict";
import { accessStatus } from "../src/security.ts";

test("unauthorized POST is rejected before reading credentials", () => {
  assert.equal(accessStatus("POST", "/", null, "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/", "Bearer incorrect", "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/", "strong-secret", "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/", "Bearer strong-secret", undefined), 401);
  assert.equal(accessStatus("POST", "/", "Bearer ", ""), 401);
});

test("only exact Bearer key grants access", () => {
  assert.equal(accessStatus("POST", "/", "Bearer strong-secret", "strong-secret"), null);
  assert.equal(accessStatus("POST", "/", "bearer strong-secret", "strong-secret"), 401);
});

test("unsupported methods and paths are not routed to login", () => {
  assert.equal(accessStatus("GET", "/", "Bearer strong-secret", "strong-secret"), 404);
  assert.equal(accessStatus("POST", "/health", "Bearer strong-secret", "strong-secret"), 404);
  assert.equal(accessStatus("POST", "/other", "Bearer strong-secret", "strong-secret"), 404);
});

test("URL-only validation endpoint requires the same Bearer key", () => {
  assert.equal(accessStatus("POST", "/validate", null, "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/validate", "Bearer incorrect", "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/validate", "Bearer strong-secret", "strong-secret"), null);
  assert.equal(accessStatus("GET", "/validate", "Bearer strong-secret", "strong-secret"), 404);
});

test("Browser Run self-check requires the same Bearer key", () => {
  assert.equal(accessStatus("POST", "/browser-check", null, "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/browser-check", "Bearer incorrect", "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/browser-check", "Bearer strong-secret", "strong-secret"), null);
  assert.equal(accessStatus("GET", "/browser-check", "Bearer strong-secret", "strong-secret"), 404);
});

test("public login-page inspection requires bearer authorization", () => {
  assert.equal(accessStatus("POST", "/login-page-check", null, "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/login-page-check", "Bearer wrong", "strong-secret"), 401);
  assert.equal(accessStatus("POST", "/login-page-check", "Bearer strong-secret", "strong-secret"), null);
  assert.equal(accessStatus("GET", "/login-page-check", "Bearer strong-secret", "strong-secret"), 404);
});
