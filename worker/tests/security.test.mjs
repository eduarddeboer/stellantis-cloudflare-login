import test from "node:test";
import assert from "node:assert/strict";
import { accessStatus, loginRateLimitStatus } from "../src/security.ts";
import { readFileSync } from "node:fs";

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


test("login quota allows an authenticated attempt and uses a static nonsecret key", async () => {
  const keys = [];
  const status = await loginRateLimitStatus({ limit: async ({key}) => {
    keys.push(key);
    return { success: true };
  }});
  assert.equal(status, null);
  assert.deepEqual(keys, ["oauth-login"]);
});

test("login quota denies exhausted attempts with HTTP 429", async () => {
  const status = await loginRateLimitStatus({ limit: async () => ({ success: false }) });
  assert.equal(status, 429);
});

test("unavailable, invalid and failing rate limit binding fail closed", async () => {
  assert.equal(await loginRateLimitStatus(undefined), 503);
  assert.equal(await loginRateLimitStatus({limit: async () => ({})}), 503);
  assert.equal(await loginRateLimitStatus({limit: async () => { throw Error("secret-in-error"); }}), 503);
});

test("login gate is the only rate decision, after auth and URL checks and before browser launch", () => {
  const code = readFileSync(new URL("../src/index.ts", import.meta.url), "utf8");
  const auth = code.indexOf("const deniedStatus = accessStatus(");
  const body = code.indexOf('if (!body || typeof body.url !== "string"');
  const allowedTarget = code.indexOf("allowedLoginUrl(target.href,");
  const gate = code.indexOf("const loginGate = await loginRateLimitStatus(env.LOGIN_RATE_LIMITER);");
  const launchBrowser = code.indexOf("browser = await launch(env.BROWSER);");
  assert.ok(auth >= 0 && body > auth && allowedTarget > body && gate > allowedTarget && launchBrowser > gate);
  assert.equal(code.split("loginRateLimitStatus(env.LOGIN_RATE_LIMITER)").length - 1, 1);
  assert.ok(code.includes('if (pathname === "/browser-check")'));
  assert.ok(code.includes('if (pathname === "/validate")'));
  assert.ok(code.includes('if (pathname === "/login-page-check")'));
  assert.ok(code.includes("if (loginGate !== null)"));
});

test("Wrangler binds isolated login quotas for default and staging", () => {
  const wrangler = readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8");
  assert.ok(wrangler.includes('[[ratelimits]]'));
  assert.ok(wrangler.includes('[[env.staging.ratelimits]]'));
  assert.equal((wrangler.match(/name = "LOGIN_RATE_LIMITER"/g) || []).length, 2);
  assert.equal((wrangler.match(/limit = 3/g) || []).length, 2);
  assert.equal((wrangler.match(/period = 60/g) || []).length, 2);
});
