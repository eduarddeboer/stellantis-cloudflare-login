import test from "node:test";
import assert from "node:assert/strict";
import { extractAuthorizationCode, allowedLoginUrl } from "../src/oauth.ts";

test("extracts callback code and decodes query parameters", () => {
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?code=a%2Bb%3D"), "a+b=");
});
test("rejects other schemes and ambiguous callbacks", () => {
  assert.equal(extractAuthorizationCode("https://evil.test/?code=secret"), null);
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?code=a&code=b"), null);
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?error=denied"), null);
});
test("host allowlist matches exactly", () => {
  const hosts = "login.example.com,auth.example.com";
  assert.equal(allowedLoginUrl("https://login.example.com/oauth", hosts), true);
  assert.equal(allowedLoginUrl("https://login.example.com.evil.test", hosts), false);
  assert.equal(allowedLoginUrl("http://login.example.com", hosts), false);
  assert.equal(allowedLoginUrl("https://user:pass@login.example.com", hosts), false);
});

test("rejects empty, oversized and duplicate authorization codes", () => {
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?code="), null);
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?code=" + "a".repeat(4097)), null);
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?code=first&code=second"), null);
});

test("rejects login URL bypass attempts", () => {
  const hosts = "login.example.com";
  assert.equal(allowedLoginUrl("https://LOGIN.EXAMPLE.COM/path", hosts), true);
  assert.equal(allowedLoginUrl("https://login.example.com@evil.example", hosts), false);
  assert.equal(allowedLoginUrl("https://login.example.com:8443/path", hosts), false);
  assert.equal(allowedLoginUrl("https://sub.login.example.com/path", hosts), false);
  assert.equal(allowedLoginUrl("https://login.example.com./path", hosts), false);
  assert.equal(allowedLoginUrl("https://login.example.com/path", ""), false);
});

test("accepts official PSA callback schemes and rejects arbitrary callbacks", () => {
  for (const scheme of ["mymap", "mymacsdk", "mymdssdk", "mymopsdk", "mymvxsdk"]) {
    assert.equal(extractAuthorizationCode(`${scheme}://oauth2redirect/nl-NL?code=auth%2Bcode`), "auth+code");
  }
  assert.equal(extractAuthorizationCode("mym://callback?code=old"), null);
  assert.equal(extractAuthorizationCode("mymap://other-host/nl-NL?code=stolen"), null);
  assert.equal(extractAuthorizationCode("mymap://oauth2redirect/nl-NL?error=access_denied"), null);
});
