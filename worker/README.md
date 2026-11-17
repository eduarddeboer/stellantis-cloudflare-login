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
