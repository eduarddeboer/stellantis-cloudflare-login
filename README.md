# Stellantis Cloudflare Login

**Experimental community release candidate — do not use on production Home Assistant.**

This is an unofficial community project comprising:

- `custom_components/stellantis_vehicles/` — the Stellantis Vehicles Home Assistant integration, based on upstream 2026.10.3, maintained here as **2026.10.3-beta.3**.
- `worker/` — source of the Cloudflare Browser Rendering Worker. **Each user deploys and owns their own Worker** and keeps their credentials and API key outside GitHub.

The Worker requests an OAuth *authorization code*. Home Assistant remains the owner of token exchange, token refresh and vehicle data access. The project is not affiliated with Stellantis, Peugeot, Cloudflare, Home Assistant, or upstream authors.

## Acceptance status (17 November 2026)

This fork is **not production-ready**. Verified results to date:

**Local acceptance evidence (17 November 2026, macOS):** commit
`2a63f7a` on `feat/open-source-worker-v03rc` passed
`bash scripts/check_local.sh`: **45 Python tests, 34 Worker tests**,
Python compilation, Worker TypeScript typecheck, and a valid,
deterministic HACS ZIP (**44 integration files, 135306 bytes**).
Wrangler's staging dry-run reported `BROWSER`,
`LOGIN_RATE_LIMITER` (3 requests / 60 seconds) and
`ALLOWED_LOGIN_HOSTS` bindings. The script reported `PASS`.
The separate release-tag build
`python3 scripts/build_release_zip.py --release-tag 2026.10.3-beta.3`
reported `VALID`. The builder's SHA-256, the separate tagged build's
SHA-256 and macOS `shasum -a 256` agreed exactly:

```text
0dba11ba3c349f811babdffa9b8225a81f5100e7a47aed8f4f1a8116c9c3c8be
```

The checksum identifies the **locally built** archive, not a published
GitHub release attachment. This is **offline packaging acceptance**,
not a Marketplace installation. No new live OAuth, rate-limit
exhaustion, Cloudflare deployment, or production Home Assistant
test was performed.

**Source-locked local acceptance (17 November 2026, macOS):** commit
`d999dd74f50e83146cc0d827b8868ade4d672be3` passed
`bash scripts/check_local.sh` (final `PASS`, with offline Python and Worker
checks and a Wrangler staging dry-run). The separate command with
`--release-tag 2026.10.3-beta.3 --expected-commit
d999dd74f50e83146cc0d827b8868ade4d672be3` reported
`SOURCE: ... (clean checkout)`, `VALID` and `SHA256`:
`0dba11ba3c349f811babdffa9b8225a81f5100e7a47aed8f4f1a8116c9c3c8be`.
The displayed Mac excerpt does not repeat the Python/Worker test counts;
the local acceptance script completed without error. The asset is still
only a **local** build and has not been published or installed via Marketplace.


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

**Security review in progress:** the Worker now applies its canonical
OAuth authorization-URL policy to credential-bearing requests, checks
registered Stellantis mobile callback schemes, and rejects a changed
top-level login hostname before filling credentials. The hardened Worker
passed the Mac offline acceptance on commit `beb6a18` (`PASS`
reported without the detailed test log). It has **not** been
redeployed to staging; genuine Peugeot redirects still require the
safe read-only diagnosis. Passing offline tests does not prove that
the complete real-account login succeeds.

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

## Next isolated acceptance: public login page only

After the strict Worker OAuth URL policy passed its Mac offline tests on
commit `beb6a18`, the next test is intentionally **credential-free**.
The first Mac run of the read-only diagnostic tests on commit `8f2fb00`
found a **false-positive assertion**: the public OAuth `scope`
legitimately contains the word `email`. The request body itself has
only a `url` field, not an email or password field. The assertion is
now structural, and redirected HTTP error responses are closed to avoid
a Python 3.14 `ResourceWarning`. The follow-up Mac run on
commit `1a2973c` was reported **PASS** (59 Python and 39 Worker tests
expected; detailed log not supplied). **The credential-free staging
diagnosis remains unconfirmed** until its separate HTTP/status output
is available:

```sh
python3 scripts/check_staging_readonly.py
```

This prompts for the owner's staging Worker root URL and hidden
`API_KEY`. It constructs MyPeugeot NL's public OAuth authorize URL from
the committed integration configuration and calls only read-only
`/validate` and `/login-page-check`. It never submits Peugeot
credentials, follows Worker redirects, publishes code, or exchanges tokens.
Interpret the safe diagnostic page categories and HTTP status as evidence
about the **currently deployed staging Worker only**. Its version has
not yet been confirmed to contain the latest security code.
A read-only `502` is not proof that a real login fails.
Do **not** deploy the changed Worker or test with the live account
before reviewing these results and any official provider redirects.

## Staging check: HTTP 403, unresolved (17 November 2026)

The Mac run on commit `1a2973c` passed **59 Python and 39 Worker
tests** (including typechecking and the staging Wrangler dry-run).
The separate credential-free staging probe then returned
`Host allowlist: HTTP 403; allowed=False` and correctly skipped the
public-page Browser Rendering test. **The HTTP 403 is not a validated
allowlist decision**, and the public Peugeot login page was not tested.

A source/target discrepancy was identified: `worker/wrangler.toml`
declares `stellantis-cloudflare-login` with a `staging` environment,
which ordinarily targets Worker service
`stellantis-cloudflare-login-staging`. The hostname previously used
in the probe contained `stellantis-cloudflare-worker-staging` instead.
That discrepancy is confirmed; whether it caused HTTP 403 is **not yet
proven**. Cloudflare Access/Browser Integrity Check is another possible
cause (especially for the default Python urllib User-Agent).

**Follow-up evidence:** `npx wrangler deployments list --env staging`
showed an Upload (19:31:45 UTC) and subsequent Secret Change (19:33:21 UTC)
on 17 November 2026. Both the canonical
`stellantis-cloudflare-login-staging` and the older-looking
`stellantis-cloudflare-worker-staging` hostname responded with HTTP 200
to unauthenticated `GET /health` using a descriptive User-Agent.
This **does not prove that both point to the same Worker, or what
source commit was deployed**. The existing Worker does not emit
HTTP 403 for `POST /validate`. The unauthenticated `POST /validate`
comparison isolated a **User-Agent-dependent rejection** on both hosts:
`Python-urllib/3.14` returned HTTP 403 while
`stellantis-staging-check/1.0` returned HTTP 401 (the expected
unauthenticated Worker response) on each host. The specific Cloudflare
protection rule was **not** independently identified. This is not an
OAuth host-allowlist failure. The existing read-only Python diagnostic
now sets that confirmed descriptive User-Agent in the outgoing request;
it does not change Worker runtime code, security rules or Bearer
authentication. The fix is **pending local regression acceptance**.
After that, the next stage is to run the credential-free diagnostic
against the verified own canonical staging Worker, not the older
ambiguous hostname. No MyPeugeot credentials are needed.

The local diagnostic was corrected to label non-200 host checks
`result=unverified`, with regressions for both 403 and the normal
200 → public-page sequence. **This improvement is awaiting Mac tests.**
Do not repeat the authenticated `/validate` request until the intended
deployment/hostname is established. Do not reveal an API key,
lower access controls, deploy the Worker, or enter Peugeot credentials
merely to overcome this unresolved 403. If the previously contacted
hostname turns out not to be your own trusted Worker, rotate the Worker
API key through Cloudflare before any further authenticated request.
See `worker/README.md`.

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

### Release source provenance

The manifest version alone cannot prove which Git commit produced a ZIP:
`main` and the development branch may both declare the same version.
For a **final release-candidate build**, first check out the exact full
40-character commit that passed acceptance, with no uncommitted files, then
use the additional source guard:

```sh
git status --short
git rev-parse HEAD
python3 scripts/build_release_zip.py \
  --release-tag 2026.10.3-beta.3 \
  --expected-commit "$ACCEPTED_RELEASE_COMMIT"
```

Set `ACCEPTED_RELEASE_COMMIT` to the **full SHA from the accepted test
evidence**, not automatically to whatever `git rev-parse HEAD` prints.
The builder verifies the full SHA matches `HEAD` and refuses to build from
a dirty checkout, missing Git metadata, or mismatched commit. It does not
create a tag, publish an asset, or deploy a Worker. A dry-run without
`--expected-commit` remains available for ordinary local development.

**Marketplace source selection:** before the first GitHub release, the
Marketplace uses the default branch (`main`). It does **not** install
unmerged PR branch code just because the repository was added from a link.
Do not install the current default branch as if it were the accepted PR.
Only perform the tagged prerelease installation test after the exact
accepted commit has a matching GitHub prerelease and verified ZIP asset.

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
listing requires a repository description and topics (**both verified
present on 17 November 2026**), a published GitHub release, and passing
official HACS and hassfest validations.
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
