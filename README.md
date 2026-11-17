# Stellantis Cloudflare Login

**Experimental community release candidate — do not use on production Home Assistant.**

This is an unofficial community project comprising:

- `custom_components/stellantis_vehicles/` — the Stellantis Vehicles Home Assistant integration, based on upstream 2026.10.3, maintained here as **2026.10.3-beta.3**.
- `worker/` — source of the Cloudflare Browser Rendering Worker. **Each user deploys and owns their own Worker** and keeps their credentials and API key outside GitHub.

The Worker requests an OAuth *authorization code*. Home Assistant remains the owner of token exchange, token refresh and vehicle data access. The project is not affiliated with Stellantis, Peugeot, Cloudflare, Home Assistant, or upstream authors.

## Status (17 November 2026)

The original separate staging Worker has obtained an OAuth authorization code in a controlled MyPeugeot NL test. An earlier isolated release candidate passed 40 offline tests. **Neither result proves that the combined distribution is ready to install:** Marketplace packaging, full Home Assistant login, token exchange, refresh, reauthentication, and rollback still require isolated tests. Do not replace the working integration or change Energie-regisseur.

## Safe setup

1. Read [Worker setup](worker/README.md) and deploy **your own** Cloudflare Worker to staging; never use an unknown third-party Worker for account credentials.
2. Install the Home Assistant fork only in a separate test VM with a verified snapshot and backup including configuration entries. It uses the **same domain** as the upstream integration, so the two must not coexist.
3. Test OAuth code generation, full token exchange, token refresh, reauthentication, and rollback before considering production.
4. The Marketplace preview may be tested only after a valid prerelease package is built and checked. A green CI status or `/health` response is not sufficient.

## Contributions

Please see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are proposed through PRs, reviewed and checked without real account credentials. The root [LICENSE](LICENSE) covers original code; [LICENSE-UPSTREAM-MIT](LICENSE-UPSTREAM-MIT) preserves upstream Stellantis Vehicles attribution.

This repository is the **canonical public product source**. The original private Worker repository remains historical staging reference; do not implement diverging runtime behavior in two repositories.
