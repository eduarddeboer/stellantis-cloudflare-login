## Observed behavior and evidence

Describe the problem without credentials, codes, tokens, cookies or raw OAuth URLs.

## Architectural owner and change

State whether this belongs to the Worker, HA integration, or packaging; explain the smallest fix.

## Checks

- [ ] Worker typecheck, tests, and Wrangler dry-run pass (or not applicable)
- [ ] HA Python files compile (or not applicable)
- [ ] Normal behavior and original failure case covered
- [ ] Trust, redirect, login/refresh and adjacent-layer regressions considered
- [ ] No live account login, secrets, unreviewed deployment, or sensitive logging in CI

## Documentation and traceability

- [ ] Existing owner documentation updated for changed behavior, setup, security,
      limitations, or release steps (or explicitly marked not applicable)
- [ ] User-facing strings/translations synchronized where relevant
- [ ] Acceptance evidence identifies tested commit, date, test environment,
      and pass/fail; untested functionality is explicitly noted
- [ ] No new, duplicate runtime documentation or contradictory instructions

## Manual acceptance still required

List staging OAuth, HA token exchange, refresh, reauth, Marketplace release ZIP, and rollback checks as applicable. A green CI check is insufficient for production.
