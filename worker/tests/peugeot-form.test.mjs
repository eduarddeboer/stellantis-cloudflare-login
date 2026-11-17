import test from "node:test";
import assert from "node:assert/strict";
import {
  EMAIL_SELECTORS, PASSWORD_SELECTORS, LOGIN_BUTTON_SELECTORS,
  CONSENT_BUTTON_SELECTORS, firstVisible,
} from "../src/peugeot-form.ts";

test("Peugeot flow supports both old and new login submit elements", () => {
  assert.ok(LOGIN_BUTTON_SELECTORS.includes('#gigya-login-form button[type="submit"]'));
  assert.ok(LOGIN_BUTTON_SELECTORS.includes('#gigya-login-form input[type="submit"]'));
  assert.ok(CONSENT_BUTTON_SELECTORS.includes("#consentbutton"));
  assert.ok(CONSENT_BUTTON_SELECTORS.includes('#cvs_from input[type="submit"]'));
  assert.ok(CONSENT_BUTTON_SELECTORS.includes('#cvs_form button[type="submit"]'));
  assert.ok(EMAIL_SELECTORS.includes('#gigya-login-form input[name="username"]'));
  assert.ok(PASSWORD_SELECTORS.includes('#gigya-login-form input[name="password"]'));
});

test("firstVisible matches visible candidates concurrently with the full timeout", async () => {
  const requestedSelectors = [];
  const found = await firstVisible(
    selector => {
      requestedSelectors.push(selector);
      return {
        async waitFor({ state, timeout }) {
          assert.equal(state, "visible");
          assert.equal(timeout, 9000);
          // Simulates a Playwright union locator that skips a hidden Gigya
          // template and resolves when any candidate becomes visible.
          assert.equal(selector, "#template:visible, #active:visible, #other:visible");
        },
        selector,
      };
    },
    ["#template", "#active", "#other"],
    9000,
  );
  assert.equal(found.selector, "#template:visible, #active:visible, #other:visible");
  assert.equal(requestedSelectors.length, 1);
});

test("firstVisible does not lose time on sequentially hidden Gigya selectors", async () => {
  let calls = 0;
  await firstVisible(
    selector => ({
      async waitFor({ timeout }) {
        calls++;
        assert.equal(timeout, 25000);
        assert.ok(selector.includes('#gigya-login-form input[name="username"]:visible'));
        assert.ok(selector.includes('input[name="email"]:visible'));
      },
    }),
    EMAIL_SELECTORS,
    25000,
  );
  assert.equal(calls, 1);
});

test("firstVisible fails closed for an empty selector list", async () => {
  await assert.rejects(
    () => firstVisible(() => { throw Error("should not run"); }, [], 1000),
    /Expected visible form control not found/,
  );
});

test("firstVisible fails without printing DOM or account data", async () => {
  await assert.rejects(
    () => firstVisible(
      selector => ({ async waitFor() { throw Error("Secret HTML: password=xxxx"); }, selector }),
      ["#missing"],
      1000,
    ),
    error => error.message === "Expected visible form control not found",
  );
});
