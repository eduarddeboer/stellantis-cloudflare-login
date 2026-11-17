#!/usr/bin/env bash
# Full offline/credential-free preflight on the developer's own computer.
# Never deploys a Worker, publishes a release, or logs into a vehicle account.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Stellantis local acceptance ==="
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short HEAD)"

command -v python3 >/dev/null || { echo "ERROR: python3 is missing" >&2; exit 1; }
command -v npm >/dev/null || { echo "ERROR: npm is missing" >&2; exit 1; }

echo "CHECK: git diff --check"
git diff --check

echo "CHECK: Python syntax"
python3 -m compileall -q custom_components/stellantis_vehicles tests

echo "CHECK: Python regression tests"
python3 -m unittest discover -s tests -v

echo "CHECK: deterministic local HACS release ZIP (not published)"
python3 scripts/build_release_zip.py

echo "CHECK: locked Worker dependencies"
npm --prefix worker ci --no-audit --no-fund

echo "CHECK: Worker TypeScript"
npm --prefix worker run check

echo "CHECK: Worker unit tests"
npm --prefix worker test

echo "CHECK: Wrangler staging bundle dry-run (no deployment)"
(
  cd worker
  npx wrangler deploy --dry-run --env staging --outdir ./dist
)

echo "CHECK: resulting tracked-file diff"
git diff --check

echo "PASS: all local checks completed. No Cloudflare deployment, GitHub release, or real account login."
