# Contributing

Contributions are welcome. This experimental project handles account authentication and requires a higher review standard than a typical UI integration.

## Workflow

1. Search existing issues and PRs; describe observable behavior and impact **without any account credentials or full OAuth URLs**.
2. Identify the owner: `worker/src/` owns browser/OAuth-code retrieval; `custom_components/stellantis_vehicles/` owns HA configuration, token exchange and refresh; root files own packaging and release checks. **Do not introduce a second login client or token controller.**
3. Fork the repository, create a focused feature branch and submit a PR against `main`. Include evidence, a minimal source fix, tests for success and failure paths, and any required translations.
4. Allow CI to validate the change. Do not run automated real-account logins, request access to others' accounts, deploy on PR, or change live Home Assistant systems.
5. Security-relevant changes to trust checks, redirects, credentials, sessions, token handling or releases need explicit maintainer review and separate isolated acceptance.

## Offline checks

```sh
cd worker
npm install --no-audit --no-fund
npm run check
npm test
npx wrangler deploy --dry-run
cd ..
python3 -m compileall -q custom_components/stellantis_vehicles
```

Never include personal email addresses, passwords, API keys, OAuth authorization codes, tokens, browser cookies, private HTML, or raw OAuth callback URLs in issues, commits, logs or tests. For security reports see [SECURITY.md](SECURITY.md).

Please preserve attribution and the licenses of third-party components.
