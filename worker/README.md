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

## API

- Public `GET /health` checks configuration presence, **not** login readiness.
- Bearer-authenticated `POST /` accepts `{ "url": "...", "email": "...", "password": "..." }` and returns `{ "code": "..." }` on success.
- Bearer-authenticated `POST /validate` checks a proposed login URL without a browser.
- Bearer-authenticated `POST /browser-check` checks Browser Rendering without Peugeot credentials.
- Bearer-authenticated `POST /login-page-check` examines only the public login page and does not submit credentials.

Browser limits, changes in login form, CAPTCHA and other interactive verification can cause legitimate failure. No CAPTCHA bypass is implemented. The Worker applies a Cloudflare Rate Limiting binding to **authenticated, well-formed `POST /` login requests** before opening a browser: **3 attempts per 60 seconds per Cloudflare location**. Rejected attempts receive HTTP 429. If the binding is missing or fails, login fails closed with HTTP 503. This does not rate-limit `GET /health`, `POST /validate` or the two diagnosis endpoints. The fixed quota key is not a password, email, API key, IP address, token or authorization code. **This limit is approximate and cannot guarantee a global concurrency cap or prevent all login bursts.** Cloudflare Browser Rendering quota limits apply independently.

The `[[ratelimits]]` and `[[env.staging.ratelimits]]` bindings in `wrangler.toml` are environment-specific, with different namespace IDs. If you already use either namespace ID within the same Cloudflare account, choose your own distinct positive-integer IDs. Never remove a rate-limit binding without also changing the login policy; an unbound login intentionally responds HTTP 503. Any production deployment still needs isolated end-to-end and rollback acceptance.

**Never run real account logins in GitHub Actions or publish logs containing email/password, codes, tokens, cookies or OAuth URLs with query parameters.**
