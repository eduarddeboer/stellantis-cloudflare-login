# Self-hosted Cloudflare OAuth Worker

This Worker uses Cloudflare Browser Rendering with `@cloudflare/playwright` to retrieve the OAuth authorization code from the user's own Stellantis/Peugeot account. It does **not** exchange, refresh or persist OAuth tokens, nor control a vehicle. Every user must deploy a **separate, account-owned Worker**. Never provide credentials to a Worker owned by someone else.

## Prerequisites

- Node.js 24 or later and npm.
- Your own Cloudflare account with Browser Rendering access (check plan, quotas and relevant charges).
- An exact, independently verified OAuth login hostname in `ALLOWED_LOGIN_HOSTS`, with no wildcards.
- An `API_KEY` stored as a **Cloudflare Secret**, never in `wrangler.toml`, GitHub, a screenshot, or chat.
- An isolated, restorable Home Assistant VM for end-to-end testing.

## Build and deploy to staging

From this `worker` directory:

```sh
npm install --no-audit --no-fund
npm run check
npm test
npx wrangler deploy --dry-run
npx wrangler login
npx wrangler secret put API_KEY --env staging
npx wrangler deploy --env staging
```

The staging deployment is **explicit**; no CI workflow deploys a Worker. `wrangler.toml` has a separate staging environment and a verified MyPeugeot NL hostname from the earlier test. Verify the OAuth URL/hostname of your own app before extending the allowlist. Confirm the output `*.workers.dev` hostname is in **your** account before entering credentials or an API key in Home Assistant.

## Confirm the exact staging Worker identity before testing

The canonical `worker/wrangler.toml` has
`name = "stellantis-cloudflare-login"` and `[env.staging]` with
`workers_dev = true`, without a staging name override. Wrangler therefore
targets the **service named `stellantis-cloudflare-login-staging`**;
the expected workers.dev hostname is
`stellantis-cloudflare-login-staging.<YOUR_ACCOUNT_SUBDOMAIN>.workers.dev`.
The real URL must still be verified against the Cloudflare dashboard or
deployment output; an earlier manually deployed Worker can have another
name. Never assume that a plausible workers.dev hostname identifies
the intended or trusted Worker.

Safe read-only checks from the `worker/` directory:

```sh
npx wrangler deployments list --env staging
```

For an independent *unauthenticated* availability check, use `GET /health`
with a descriptive User-Agent and inspect **only its HTTP status**. This
does not submit an API key or Peugeot credentials and cannot by itself
prove the Worker's code/version. HTTP 403 from a diagnostic request is
**not a valid `allowed: false` response** from `POST /validate`: this
repository's Worker returns 200 (with an explicit boolean), 401 for
a rejected API key, 400/415 for malformed input, or 404 for an unsupported
path, not 403. A 403 may originate from a different deployed Worker or
from Cloudflare's access controls or Browser Integrity Check. The default
Python `urllib` User-Agent is a known reason for Cloudflare-managed
workers.dev blocks. Verify the hostname and origin of the response
**before** changing code, keys, permissions or security policy.
The local script now reports `result=unverified` for a non-200
`/validate` response instead of displaying `allowed=False` as though
a provider-host decision had been obtained.

## Follow-up evidence: both health endpoints respond (17 November 2026)

`wrangler deployments list --env staging` returned two deployment records:
an Upload at 19:31:45 UTC and a subsequent Secret Change at 19:33:21 UTC.
This establishes that Wrangler can inspect the configured staging service,
but not which Git commit or code revision was deployed. Both
`stellantis-cloudflare-login-staging` (canonical Wrangler service name)
and the older-looking `stellantis-cloudflare-worker-staging` hostname
returned **HTTP 200** to unauthenticated `GET /health` with a custom
User-Agent. These checks prove that both endpoints answer, **not** that
both belong to the same service or use the current code.

The earlier `POST /validate` with Python `urllib` returned HTTP 403.
The repository's existing Worker authorization logic never returns 403
for that path. Cloudflare documents that `workers.dev` can reject the
default Python urllib User-Agent *before* the Worker runs, while a
descriptive application User-Agent is allowed. This is a strong
hypothesis, not a confirmed root cause.

**Confirmed User-Agent comparison (17 November 2026):** four
unauthenticated `POST /validate` requests, differing only in User-Agent,
produced:

| Staging host | `Python-urllib/3.14` | `stellantis-staging-check/1.0` |
| --- | --- | --- |
| `stellantis-cloudflare-login-staging` | HTTP 403 | HTTP 401 |
| `stellantis-cloudflare-worker-staging` | HTTP 403 | HTTP 401 |

An HTTP 401 without a Bearer key is the Worker's expected response.
This demonstrates a User-Agent-dependent rejection in front of the
Worker on both endpoints. **Which exact Cloudflare rule rejects urllib
is not established**; there is no evidence here of a broken hostname
allowlist. Both hostnames responding the same way does not establish
that they run the same deployment.

The canonical local `scripts/check_staging_readonly.py` now sends the
already-tested descriptive `User-Agent: stellantis-staging-check/1.0`
on both diagnostic requests. No access policy, Worker runtime,
Bearer-secret handling, or allowed-host configuration was changed.
The additional offline regression test and Mac acceptance are pending.
Once local tests pass, use only the **confirmed, account-owned
canonical** staging hostname for the read-only probe.

## Credential-free staging acceptance from your Mac

After `bash scripts/check_local.sh` passes, run this **read-only**
inspection from the repository root:

```sh
python3 scripts/check_staging_readonly.py
```

Enter the root HTTPS URL of **your own** staging `NAME.ACCOUNT.workers.dev`
Worker, followed by its `API_KEY` (entered with hidden input). Never paste
the key into GitHub, chat, a shell command, or test output. The script uses
the committed MyPeugeot NL OAuth configuration to create the *public*
authorize URL locally; it does not read or request a Peugeot email or password.

Only authenticated `POST /validate` (host allowlist) and
`POST /login-page-check` (public-page Browser Rendering inspection) are
called. The local script does **not** call the credential-bearing `POST /`,
submit login forms, exchange tokens, follow HTTP redirects from the Worker,
or print URLs, credentials, response bodies, or HTML. The reported HTTP
status, fixed page category, stage/reason and form-visibility booleans are
safe to share. A `502` can mean that Peugeot shows an email-first or
challenge flow and **does not** prove the login works or fails.

**Crucial distinction:** this checks the Worker version **currently deployed**
to staging. It does **not** test a newly committed OAuth policy until that
Worker version has been deliberately deployed to staging after local
acceptance. Do not deploy or enter real Peugeot credentials as part of this
diagnosis. If you see a different identity-host category, investigate the
official redirect flow before changing `ALLOWED_LOGIN_HOSTS`; never add a
hostname merely to suppress a failure.

## API

- Public `GET /health` checks configuration presence, **not** login readiness.
- Bearer-authenticated `POST /` accepts `{ "url": "...", "email": "...", "password": "..." }` and returns `{ "code": "..." }` on success.
- Bearer-authenticated `POST /validate` checks **only the exact HTTPS provider-host allowlist** without a browser; `allowed: true` does not validate the OAuth path/redirect or prove login readiness. The stricter `POST /login-page-check` validates the complete authorize URL.
- Bearer-authenticated `POST /browser-check` checks Browser Rendering without Peugeot credentials.
- Bearer-authenticated `POST /login-page-check` examines only the public login page and does not submit credentials.

Browser limits, changes in login form, CAPTCHA and other interactive verification can cause legitimate failure. No CAPTCHA bypass is implemented. The Worker applies a Cloudflare Rate Limiting binding to **authenticated, well-formed `POST /` login requests** before opening a browser: **3 attempts per 60 seconds per Cloudflare location**. Rejected attempts receive HTTP 429. If the binding is missing or fails, login fails closed with HTTP 503. This does not rate-limit `GET /health`, `POST /validate` or the two diagnosis endpoints. The fixed quota key is not a password, email, API key, IP address, token or authorization code. **This limit is approximate and cannot guarantee a global concurrency cap or prevent all login bursts.** Cloudflare Browser Rendering quota limits apply independently.

## OAuth authorize URL and navigation trust

The credential-bearing `POST /` endpoint and the read-only
`POST /login-page-check` endpoint use the **same canonical URL policy**:
only an HTTPS OAuth authorization URL on an explicitly allowlisted
provider host at `/am/oauth2/authorize`, with the required OAuth
parameters and a Stellantis/PSA mobile-app callback
(`mymap`, `mymacsdk`, `mymdssdk`, `mymopsdk` or `mymvxsdk`) is accepted.
Unexpected/duplicate query parameters and arbitrary third-party
redirect URIs are rejected before opening the browser.

After browser navigation the Worker verifies that the top-level login
page remains on the exact allowlisted host before inserting the email
or password. **This is a fail-closed safety check, not a claim that
all redirects are harmless.** Some legitimate Peugeot login journeys
might use a different main-frame host; the stricter policy must be
verified in staging before any live account-based acceptance. Do not
extend the hostname allowlist just to bypass a failure without first
verifying the official provider flow. Read-only `/validate` and
`/login-page-check` can diagnose the provider without submitting
credentials.

The `[[ratelimits]]` and `[[env.staging.ratelimits]]` bindings in `wrangler.toml` are environment-specific, with different namespace IDs. If you already use either namespace ID within the same Cloudflare account, choose your own distinct positive-integer IDs. Never remove a rate-limit binding without also changing the login policy; an unbound login intentionally responds HTTP 503. Any production deployment still needs isolated end-to-end and rollback acceptance.

**Never run real account logins in GitHub Actions or publish logs containing email/password, codes, tokens, cookies or OAuth URLs with query parameters.**
