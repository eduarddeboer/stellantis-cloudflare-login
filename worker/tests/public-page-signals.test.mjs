import test from "node:test";
import assert from "node:assert/strict";
import { sanitizePublicPageReport, classifyDocumentKind } from "../src/public-page-signals.ts";

const signals = {
  body_present: true, gigya_form_present: false,
  email_input_present: false, password_input_present: false,
  submit_control_present: false, cookie_dialog_present: true,
  challenge_control_present: false,
};

test("report recognizes only fixed host categories, no URLs or query tokens", () => {
  const fullUrl = "https://id-dcr.peugeot.com/oidc/secret-path?code=SECRET-CODE&email=sensitive@example.com";
  const state = sanitizePublicPageReport(fullUrl, 200, 2, signals);
  assert.equal(state.page_category, "peugeot_identity");
  assert.equal(state.iframe_count, 1);
  assert.equal(state.navigation_status, 200);
  assert.equal(state.cookie_dialog_present, true);
  const encoded = JSON.stringify(state);
  assert.equal(encoded.includes("SECRET-CODE"), false);
  assert.equal(encoded.includes("sensitive@example.com"), false);
  assert.equal(encoded.includes("secret-path"), false);
});

test("unknown domains never become user-controlled output", () => {
  const report = sanitizePublicPageReport("https://attacker.invalid/my-own-secret?x=foo", 403, 999, signals);
  assert.equal(report.page_category, "other");
  assert.equal(report.iframe_count, 12);
  assert.equal(report.navigation_status, 403);
  assert.equal(JSON.stringify(report).includes("attacker.invalid"), false);
});

test("invalid navigation metadata normalizes to safe bounds", () => {
  const report = sanitizePublicPageReport("not a URL", -1, -3, signals);
  assert.equal(report.page_category, "unknown");
  assert.equal(report.navigation_status, null);
  assert.equal(report.iframe_count, 0);
});


test("XRDS OpenID discovery document is identified without disclosing service URI", () => {
  const result = sanitizePublicPageReport(
    "https://idpcvs.peugeot.com/openid?code=TOP-SECRET", 200, 1,
    {
      ...signals,
      document_content_type: "application/xrds+xml",
      root_element_name: "XRDS",
    },
  );
  assert.equal(result.document_kind, "xrds_discovery");
  assert.equal(result.page_category, "peugeot_entry");
  assert.equal(JSON.stringify(result).includes("id-dcr.peugeot.com/login"), false);
  assert.equal(JSON.stringify(result).includes("TOP-SECRET"), false);
  assert.equal("document_content_type" in result, false);
  assert.equal("root_element_name" in result, false);
});

test("classifies regular login HTML independently from XML discovery", () => {
  assert.equal(classifyDocumentKind("text/html", "HTML"), "html");
  assert.equal(classifyDocumentKind("application/xhtml+xml", "html"), "html");
  assert.equal(classifyDocumentKind("application/xml", "XRDS"), "xrds_discovery");
  assert.equal(classifyDocumentKind("application/xml", "feed"), "xml_other");
  assert.equal(classifyDocumentKind("", ""), "unknown");
});

