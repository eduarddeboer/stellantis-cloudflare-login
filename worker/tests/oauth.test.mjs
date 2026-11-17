import test from "node:test";
import assert from "node:assert/strict";
import { extractAuthorizationCode, allowedLoginUrl, allowedAuthorizeUrl } from "../src/oauth.ts";

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


const validAuthorize = new URL("https://idpcvs.peugeot.com/am/oauth2/authorize");
validAuthorize.searchParams.set("client_id", "test-client-not-a-real-account");
validAuthorize.searchParams.set("response_type", "code");
validAuthorize.searchParams.set("redirect_uri", "mymap://oauth2redirect/nl-NL");
validAuthorize.searchParams.set("scope", "openid profile email");
validAuthorize.searchParams.set("locale", "nl-NL");

test("accepts a correctly scoped PSA authorize URL across supported callback schemes", () => {
  for (const scheme of ["mymap", "mymacsdk", "mymdssdk", "mymopsdk", "mymvxsdk"]) {
    const url = new URL(validAuthorize);
    url.searchParams.set("redirect_uri", `${scheme}://oauth2redirect/nl-NL`);
    assert.equal(allowedAuthorizeUrl(url.href, "idpcvs.peugeot.com"), true);
  }
});

test("credential-bearing authorize URL rejects arbitrary paths and third-party redirects", () => {
  const hosts = "idpcvs.peugeot.com";
  const wrongPath = new URL(validAuthorize);
  wrongPath.pathname = "/unrelated/login";
  assert.equal(allowedAuthorizeUrl(wrongPath.href, hosts), false);
  const lookalike = new URL(validAuthorize);
  lookalike.hostname = "idpcvs.peugeot.com.evil.test";
  assert.equal(allowedAuthorizeUrl(lookalike.href, hosts), false);
  for (const redirect of ["https://evil.test/login", "mymap://evil.test/nl-NL", "invalid://oauth2redirect/nl-NL"]) {
    const url = new URL(validAuthorize);
    url.searchParams.set("redirect_uri", redirect);
    assert.equal(allowedAuthorizeUrl(url.href, hosts), false);
  }
});

test("authorize URL rejects missing required fields, unexpected params and duplicate keys", () => {
  const hosts = "idpcvs.peugeot.com";
  for (const key of ["client_id", "redirect_uri", "response_type"]) {
    const url = new URL(validAuthorize);
    url.searchParams.delete(key);
    assert.equal(allowedAuthorizeUrl(url.href, hosts), false);
  }
  const duplicate = new URL(validAuthorize);
  duplicate.searchParams.append("redirect_uri", "mymap://oauth2redirect/other");
  assert.equal(allowedAuthorizeUrl(duplicate.href, hosts), false);
  const extra = new URL(validAuthorize);
  extra.searchParams.append("next", "https://evil.test");
  assert.equal(allowedAuthorizeUrl(extra.href, hosts), false);
  assert.equal(allowedAuthorizeUrl(validAuthorize.href, ""), false);
});
