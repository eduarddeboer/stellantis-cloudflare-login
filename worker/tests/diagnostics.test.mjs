import test from "node:test";
import assert from "node:assert/strict";
import { safeFailureKind, diagnostic } from "../src/diagnostics.ts";

test("classifies non-sensitive errors without disclosing raw provider response", () => {
  assert.equal(safeFailureKind(new Error("Unable to create new browser: code: 429: Browser time limit exceeded for today")), "browser_limit");
  assert.equal(safeFailureKind(new Error("Timeout 30000ms exceeded")), "timeout");
  assert.equal(safeFailureKind(new Error("selector was not found")), "browser_error");
  assert.equal(safeFailureKind(undefined), "browser_error");
});

test("diagnostics never expose OAuth URLs, credentials or provider error strings", () => {
  const raw = "token=secret-code email=private@example.invalid password=secret-password";
  const body = diagnostic("consent_submit", new Error(raw));
  assert.deepEqual(body, {
    message: "Authentication failed or timed out",
    code: 502,
    stage: "consent_submit",
    reason: "browser_error",
  });
  assert.equal(JSON.stringify(body).includes(raw), false);
  assert.equal(JSON.stringify(body).includes("secret"), false);
});
