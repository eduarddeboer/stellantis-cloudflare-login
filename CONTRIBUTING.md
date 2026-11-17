# Contributing

Contributions are welcome. This experimental project handles account authentication and requires a higher review standard than a typical UI integration.

## Workflow

1. Search existing issues and PRs; describe observable behavior and impact **without any account credentials or full OAuth URLs**.
2. Identify the owner: `worker/src/` owns browser/OAuth-code retrieval; `custom_components/stellantis_vehicles/` owns HA configuration, token exchange and refresh; root files own packaging and release checks. **Do not introduce a second login client or token controller.**
3. Fork the repository, create a focused feature branch and submit a PR against `main`. Include evidence, a minimal source fix, tests for success and failure paths, and any required translations.
4. Run `bash scripts/check_local.sh` on your development machine and report the result in the PR. Pull requests do **not** start GitHub Actions automatically; CI remains a safety net for `main` and may be manually dispatched once available on the default branch. Do not run real-account logins, request access to others' accounts, deploy on PR, or change live Home Assistant systems.
5. Security-relevant changes to trust checks, redirects, credentials, sessions, token handling or releases need explicit maintainer review and separate isolated acceptance.

## Documentation is part of the change

Keep the **existing canonical documentation** in sync with every relevant
behavioral, configuration, security, setup, or release change. Update it in
the **same PR**, rather than leaving documentation for a later release.
Do not create parallel instructions if an existing owner document suffices.

- `README.md`: product scope, current acceptance status, installation/rollback
  warnings, and prerequisites for community/HACS releases.
- `worker/README.md`: Cloudflare deployment, bindings, secrets, API behavior,
  limits, and failure modes.
- `CONTRIBUTING.md`: architecture ownership, developer workflow, and local checks.
- `SECURITY.md`: trust boundaries, credential risks, sensitive logging,
  and vulnerability reporting.
- `custom_components/stellantis_vehicles/translations/`: user-visible flow
  labels and error messages when changed, in supported locales.
- `.github/PULL_REQUEST_TEMPLATE.md`: the mandatory change/acceptance checklist.

Before marking a PR ready, confirm that code, tests, documentation, and
recorded acceptance evidence describe **the same commit**. Distinguish
offline simulation, staging observations, and live account acceptance.
Record untested or blocked scenarios explicitly; never promote a green
unit-test run into a claim of production readiness. Documentation-only
corrections do not require rerunning unrelated runtime acceptance tests.

## Local-first acceptance checks

From the repository root on your own Mac or Linux machine, run:

```sh
bash scripts/check_local.sh
```

The script compiles and tests the Home Assistant integration, builds and verifies the
deterministic HACS ZIP locally, installs Worker dependencies using `npm ci`, runs
the Worker typecheck and unit tests, and performs a **staging Wrangler dry-run**.
It never publishes a GitHub release, deploys a Cloudflare Worker, sends login
credentials, or modifies a Home Assistant instance.

Share the final PASS/FAIL and relevant error messages in the PR, **not** secrets
or complete OAuth URLs. Always rerun the script after changes to code, tests,
release packaging, or the Worker. The default branch still runs GitHub Actions
as a last release-safety check; avoid using remote runners for every PR iteration.
A passing local run does not substitute for isolated end-to-end OAuth,
installation, and rollback acceptance.

## Official checks at the release gate (not per commit)

The existing `.github/workflows/ci.yml` also contains two **manual-only**
jobs that execute the official `hacs/action@main` and
`home-assistant/actions/hassfest@master` validators. They are conditioned
on `workflow_dispatch`, so normal PR updates and pushes to `main` do
not start these extra runners. Trigger them deliberately when preparing
a public Marketplace/catalog submission, and record the run URL, commit
and outcome in the PR.

These official checks require GitHub Actions, unlike our local offline
suite. They are not substitutes for live OAuth or isolated Marketplace
installation and removal. **Do not treat a HACS validation of the
default branch as validation of an unmerged feature branch**: when no
release exists, HACS checks the default branch. Run them only when the
intended release source is on `main` or as a published release, and
verify which source was validated. A workflow can be manually dispatched
once it exists on the default branch.



Never include personal email addresses, passwords, API keys, OAuth authorization codes, tokens, browser cookies, private HTML, or raw OAuth callback URLs in issues, commits, logs or tests. For security reports see [SECURITY.md](SECURITY.md).

Please preserve attribution and the licenses of third-party components.
