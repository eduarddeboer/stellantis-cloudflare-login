# Stellantis Cloudflare Login

**Experimental community release candidate — do not use on production Home Assistant.**

This is an unofficial community project comprising:

- `custom_components/stellantis_vehicles/` — the Stellantis Vehicles Home Assistant integration, based on upstream 2026.10.3, maintained here as **2026.10.3-beta.3**.
- `worker/` — source of the Cloudflare Browser Rendering Worker. **Each user deploys and owns their own Worker** and keeps their credentials and API key outside GitHub.

The Worker requests an OAuth *authorization code*. Home Assistant remains the owner of token exchange, token refresh and vehicle data access. The project is not affiliated with Stellantis, Peugeot, Cloudflare, Home Assistant, or upstream authors.

## Acceptance status (17 November 2026)

This fork is **not production-ready**. Verified results to date:

**Local acceptance evidence (17 November 2026, macOS):** commit
`d121702` on `feat/open-source-worker-v03rc` passed
`bash scripts/check_local.sh`: **44 Python tests, 34 Worker tests**,
Python compilation, Worker TypeScript typecheck, and a valid,
deterministic HACS ZIP (**44 integration files, 135306 bytes**).
Wrangler's staging dry-run reported `BROWSER`,
`LOGIN_RATE_LIMITER` (3 requests / 60 seconds) and
`ALLOWED_LOGIN_HOSTS` bindings. The script reported `PASS`.
The separate release-tag build
`python3 scripts/build_release_zip.py --release-tag 2026.10.3-beta.3`
also reported `VALID`. Incorrect and `v`-prefixed release tags were
rejected by offline tests. This is **offline packaging acceptance**,
not a published GitHub release or Marketplace installation. No new
live OAuth, rate-limit exhaustion, Cloudflare deployment, or production
Home Assistant test was performed.


- Worker and Home Assistant offline regression checks pass, including OAuth code-to-token
  simulation, token refresh, secret-safe HTTP diagnostics, login rate limiting and
  cleanup of fictional account resources.
- A separate staging Worker responds correctly to authenticated, credential-free
  login-host validation and rejects lookalike hosts.
- The isolated Home Assistant VirtualBox lab displays the configuration form;
  installation and removal without a configured account (Test A) have passed.
  The cleanup routine was also exercised with fake account data (Test B).
- The local HACS ZIP builder is deterministic, but no published release asset or
  Marketplace install/upgrade/rollback has been accepted yet.

**Not yet accepted:** live rate-limit exhaustion (HTTP 429), full real-account
OAuth → token exchange → refresh → reauthentication, and HACS prerelease
installation/rollback. The same MyPeugeot account is used by the working
production integration; do not run another login without assessing token
invalidation risk. Never replace that production installation during development.

## Local-first developer checks

Instead of starting GitHub runners on every PR commit, run the complete
credential-free suite on your own computer from the repository root:

```sh
bash scripts/check_local.sh
```

This executes Python syntax/tests and HACS ZIP validation, Worker TypeScript
and unit tests, and a **Wrangler staging dry-run**. It does not deploy, publish,
or connect to a Peugeot account. GitHub Actions still runs on changes merged
to `main` as a final safety net; PRs are not automatically run on GitHub.

## HACS prerelease requirements

The root `hacs.json` declares `zip_release: true`. An actual GitHub release
must therefore have a version/tag corresponding to the version in
`custom_components/stellantis_vehicles/manifest.json` and a release asset
named **`stellantis_vehicles.zip`**. Before any publication, run the
full local suite and build the ZIP with an explicit, checked release tag:

```sh
bash scripts/check_local.sh
python3 scripts/build_release_zip.py --release-tag 2026.10.3-beta.3
```

The builder also prints `SHA256: <64 hexadecimal characters>` for the
exact archive bytes. Record that digest with the release acceptance evidence
and compare it to the **downloaded GitHub release asset** before approving
Marketplace installation:

```sh
shasum -a 256 dist/stellantis_vehicles.zip
shasum -a 256 /path/to/downloaded/stellantis_vehicles.zip
```

Both digests must be identical. An attached asset with the right filename but
different contents is **not accepted**. This check does not validate an OAuth
login or guarantee that the source commit has been independently audited.

The argument is an **example tied to the current manifest version**; update
it whenever `custom_components/stellantis_vehicles/manifest.json` changes.
It must match the manifest `version` exactly (including beta suffix and
without an added `v` prefix); otherwise the builder refuses to create the
ZIP. Confirm that the release will point at the accepted **canonical
repository commit**, not an older branch or an experimental private Worker.
The resulting local `dist/stellantis_vehicles.zip` is *not* published.

**Isolated prerelease acceptance plan (not yet executed):**

1. Review the release notes, source and full local test evidence for the
   exact tagged commit. Do not create a release while security/functional
   acceptance gates are still open.
2. Attach `stellantis_vehicles.zip` to a **GitHub prerelease** with the
   same exact tag as the integration manifest; a Git tag alone is not enough.
3. After publishing the candidate with the checked ZIP attachment, in a
   snapshot-protected **VirtualBox Home Assistant lab only**, open
   **Settings → Marketplace → Add from link** and enter this GitHub repository.
   Connect GitHub in Marketplace if prompted. Enable the repository's
   **Pre-release** entity/switch under **Settings → Devices & services →
   Marketplace** to offer prereleases. Confirm the selected tag and archive
   checksum, install, and open the configuration UI **without signing in
   with the production MyPeugeot account**. Home Assistant 2026.11+
   has Marketplace built in; do not install a separate HACS integration.
4. Confirm uninstall, normal restart, and restoration from the VM snapshot.
   Upgrade/downgrade acceptance additionally requires two known-good
   published versions; do not claim rollback-to-previous-version tested
   when no earlier version exists.

A local `dist/` ZIP or a successful CI run is **not** a published release.
Preserve previous published releases for future rollback.

The public Marketplace **catalog** is a separate future milestone. Catalog
listing requires a repository description and topics (currently missing),
a published GitHub release, and passing official HACS and hassfest validations.
These checks cannot be replaced by the local ZIP builder or simulated Python
OAuth tests. We will run required public validations at the release gate
instead of starting a GitHub runner for each development commit.

## Safe setup

1. Read [Worker setup](worker/README.md) and deploy **your own** Cloudflare Worker to staging; never use an unknown third-party Worker for account credentials.
2. Install the Home Assistant fork only in a separate test VM with a verified snapshot and backup including configuration entries. It uses the **same domain** as the upstream integration, so the two must not coexist.
3. Test OAuth code generation, full token exchange, token refresh, reauthentication, and rollback before considering production.
4. The Marketplace preview may be tested only after a valid prerelease package is built and checked. A green CI status or `/health` response is not sufficient.

## Contributions

Please see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are proposed through PRs, reviewed and checked without real account credentials. The root [LICENSE](LICENSE) covers original code; [LICENSE-UPSTREAM-MIT](LICENSE-UPSTREAM-MIT) preserves upstream Stellantis Vehicles attribution.

This repository is the **canonical public product source**. The original private Worker repository remains historical staging reference; do not implement diverging runtime behavior in two repositories.
