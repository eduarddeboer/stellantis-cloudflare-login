import test from "node:test";
import assert from "node:assert/strict";
import { summarizeFrameVisibility } from "../src/form-visibility.ts";

const base = {
  email_visible: false, password_visible: false, submit_visible: false,
  first_gigya_email_visible: false, challenge_widget_visible: false,
  recaptcha_present: false, hcaptcha_present: false, turnstile_present: false,
};

test("separates main frame hidden form from an iframe with visible controls", () => {
  const report = summarizeFrameVisibility([
    { ...base, recaptcha_present: true },
    { ...base, email_visible: true, password_visible: true, submit_visible: true },
    null,
  ]);
  assert.equal(report.main_email_visible, false);
  assert.equal(report.iframe_email_visible, true);
  assert.equal(report.iframe_password_visible, true);
  assert.equal(report.iframe_submit_visible, true);
  assert.equal(report.inspected_iframes, 1);
  assert.equal(report.challenge_type, "recaptcha");
  assert.equal(report.challenge_widget_visible, false);
});

test("differentiates hidden first Gigya input from another visible field", () => {
  const report = summarizeFrameVisibility([
    { ...base, email_visible: true, first_gigya_email_visible: false },
  ]);
  assert.equal(report.main_email_visible, true);
  assert.equal(report.first_gigya_email_visible, false);
  assert.equal(report.iframe_email_visible, false);
});

test("categorizes multiple providers without exposing frame URLs or text", () => {
  const secret = "https://captcha.vendor.invalid/?token=secret-code";
  const report = summarizeFrameVisibility([
    { ...base, recaptcha_present: true, challenge_widget_visible: true },
    { ...base, hcaptcha_present: true, input_url: secret },
  ]);
  assert.equal(report.challenge_type, "multiple");
  assert.equal(report.challenge_widget_visible, true);
  assert.equal(JSON.stringify(report).includes("secret-code"), false);
  assert.equal(JSON.stringify(report).includes("vendor.invalid"), false);
});

test("limits the count to twelve inspected iframes", () => {
  const report = summarizeFrameVisibility([base, ...Array.from({ length: 25 }, () => base)]);
  assert.equal(report.inspected_iframes, 12);
});

test("no results means no claims about visibility or active security challenge", () => {
  const report = summarizeFrameVisibility([]);
  assert.equal(report.main_email_visible, false);
  assert.equal(report.iframe_email_visible, false);
  assert.equal(report.challenge_type, "none");
  assert.equal(report.inspected_iframes, 0);
});
