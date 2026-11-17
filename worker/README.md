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

Browser limits, changes in login form, CAPTCHA and other interactive verification can cause legitimate failure. No CAPTCHA bypass is implemented. The Worker currently has no application-level rate limiter or explicit per-account concurrency limit: do not deploy unattended for production use without a separate security review.

**Never run real account logins in GitHub Actions or publish logs containing email/password, codes, tokens, cookies or OAuth URLs with query parameters.**
