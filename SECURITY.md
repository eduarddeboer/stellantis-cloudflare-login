# Security policy

This project is **experimental**; it is not independently security-audited or production-supported.

For a sensitive security issue, use GitHub **Report a vulnerability** (private vulnerability reporting) if enabled. Otherwise, create a public issue requesting a private reporting channel **without including any sensitive details**.

Do not disclose real passwords, account identifiers, Worker API keys, OAuth codes, refresh/access tokens, cookies or private request/response bodies publicly.

Security boundaries:

- Each user operates their own Worker, authenticated via a Cloudflare Secret used as a Bearer token.
- Only explicitly approved OAuth login hosts may receive login credentials; no wildcard domains or arbitrary redirects.
- The Worker accepts only the known Stellantis OAuth authorization path and PSA mobile-app callback schemes for credential-bearing requests. The main-frame host is checked again before entering credentials; untrusted redirects fail closed. The provider's actual redirect journey still requires staging acceptance.
- The Worker returns an authorization code; the Home Assistant integration is the sole owner of token exchange/refresh.
- Do not disable access control to accommodate a client, bypass interactive verification, or deploy external PRs automatically.
- An offline CI pass and `/health` are not evidence of live authentication or production readiness.
- The optional local staging diagnostic reads the Worker `API_KEY` through
  hidden input and invokes only `/validate` and `/login-page-check`.
  It deliberately disables redirected HTTP requests so authentication
  headers cannot be forwarded to another destination. It never accepts
  Peugeot credentials or invokes the live login endpoint. Diagnostic
  output is whitelisted to non-sensitive status categories; do not paste
  raw network traces or secrets when reporting an issue.

Never use someone else's Stellantis account without authorization.
