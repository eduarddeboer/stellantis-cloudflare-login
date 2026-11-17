#!/usr/bin/env python3
"""Credential-free, read-only staging inspection of the user's OWN Worker.

Makes POST /validate and POST /login-page-check only. Never makes POST /,
supplies a MyPeugeot email/password, deploys code or prints request URLs,
secrets, raw HTTP responses, cookies or browser HTML.
"""
from __future__ import annotations

import ast
import getpass
import importlib.util
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "custom_components" / "stellantis_vehicles" / "configs.json"
CONSTANTS = ROOT / "custom_components" / "stellantis_vehicles" / "const.py"
WORKER_CLIENT = ROOT / "custom_components" / "stellantis_vehicles" / "worker_oauth_client.py"
STAGES = frozenset({
    "browser_launch", "browser_context", "browser_page",
    "login_navigation", "login_email_field", "login_password_field",
    "login_submit", "consent_submit", "oauth_callback",
})
REASONS = frozenset({"timeout", "browser_limit", "browser_error"})
CATEGORIES = frozenset({"peugeot_entry", "peugeot_identity", "peugeot_site", "other", "unknown"})
KINDS = frozenset({"html", "xrds_discovery", "xml_other", "other", "unknown"})
VISIBILITY_KEYS = (
    "main_email_visible", "main_password_visible", "main_submit_visible",
    "iframe_email_visible", "iframe_password_visible", "iframe_submit_visible",
    "challenge_widget_visible",
)


def public_authorize_url() -> str:
    """Recreate the NL authorization URL from canonical, committed config.

    Read public, literal OAuth templates only. Never read client_secret.
    Preserve the canonical source order/encoding rather than guessing a URL.
    """
    app = json.loads(CONFIGS.read_text(encoding="utf-8"))["MyPeugeot"]
    country = app["configs"]["NL"]
    tree = ast.parse(CONSTANTS.read_text(encoding="utf-8"))
    constants = {
        target.id: node.value
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }

    def resolve(node):
        if isinstance(node, ast.Name):
            return resolve(constants[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return resolve(node.left) + resolve(node.right)
        return ast.literal_eval(node)

    url = resolve(constants["OAUTH_AUTHORIZE_URL"])
    params = resolve(constants["OAUTH_AUTHORIZE_QUERY_PARAMS"])
    full = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    placeholders = {
        "oauth_url": app["oauth_url"], "client_id": country["client_id"],
        "scheme": app["scheme"], "locale": country["locale"], "culture": "nl",
    }
    for key, value in placeholders.items():
        full = full.replace("{#" + key + "#}", value)
    if "{#" in full or "}" in full:
        raise ValueError("Unresolved OAuth configuration placeholder")
    return full


def normalized_worker_url(raw: str) -> str | None:
    """Reuse the HA canonical trusted workers.dev URL parser."""
    spec = importlib.util.spec_from_file_location("stellantis_worker_client_offline", WORKER_CLIENT)
    if spec is None or spec.loader is None:
        raise ValueError("Local Worker client unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalized_worker_url(raw)


def inspect(endpoint: str, api_key: str, path: str, authorize_url: str) -> tuple[int, dict]:
    """Only the two approved read-only endpoints, with sanitized exceptions."""
    if path not in ("/validate", "/login-page-check"):
        raise ValueError("Only read-only staging endpoints are permitted")
    payload = json.dumps({"url": authorize_url}).encode("utf-8")
    request = Request(
        endpoint.rstrip("/") + path, data=payload, method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Accept": "application/json", "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=100) as response:
            status, raw = response.status, response.read(16385)
    except HTTPError as error:
        status, raw = error.code, error.read(16385)
    except (OSError, URLError):
        raise ValueError("Staging endpoint unreachable or timed out") from None
    if len(raw) > 16384:
        raise ValueError("Unexpectedly large staging response")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid staging response format") from None
    if not isinstance(data, dict):
        raise ValueError("Invalid staging response format")
    return status, data


def safe_report(status: int, data: dict) -> list[str]:
    """Whitelist-only rendering. Never print provider/user-controlled strings."""
    report = [f"Public login page: HTTP {status}"]
    stage, reason = data.get("stage"), data.get("reason")
    if stage in STAGES:
        report.append("Stage: " + stage)
    if reason in REASONS:
        report.append("Reason: " + reason)
    if data.get("login_form") is True:
        report.append("Login form: detected (no credentials submitted)")
    page = data.get("public_page")
    if isinstance(page, dict):
        if page.get("page_category") in CATEGORIES:
            report.append("Public page category: " + page["page_category"])
        if page.get("document_kind") in KINDS:
            report.append("Document kind: " + page["document_kind"])
    visible = data.get("form_visibility")
    if isinstance(visible, dict):
        for key in VISIBILITY_KEYS:
            if isinstance(visible.get(key), bool):
                report.append(f"{key}: {visible[key]}")
    return report


def main() -> int:
    print("Stellantis staging: credential-free read-only diagnosis")
    print("Only your own *.workers.dev Worker. No Peugeot email or password.")
    worker = normalized_worker_url(input("Own staging Worker HTTPS URL: ").strip())
    if worker is None:
        print("FAIL: provide the root HTTPS URL of your own NAME.ACCOUNT.workers.dev Worker")
        return 1
    secret = getpass.getpass("Own staging Worker API_KEY (hidden): ")
    if len(secret) < 24 or len(secret) > 2048 or any(ch.isspace() for ch in secret):
        print("FAIL: invalid staging API_KEY format")
        return 1

    try:
        url = public_authorize_url()
        status, data = inspect(worker, secret, "/validate", url)
        allowed = data.get("allowed") is True
        print(f"Host allowlist: HTTP {status}; allowed={allowed}")
        if status != 200 or not allowed:
            print("STOP: read-only page inspection skipped (allowlist/auth failed)")
            return 1

        status, data = inspect(worker, secret, "/login-page-check", url)
        for line in safe_report(status, data):
            print(line)
        if status == 401:
            print("STOP: Worker API key rejected")
            return 1
        if status == 400:
            print("STOP: public OAuth URL rejected; inspect source/config before proceeding")
            return 1
        if status not in (200, 502):
            print("STOP: public page inspection returned unexpected status")
            return 1
    except (ValueError, KeyError, TypeError):
        print("STOP: cannot complete the read-only staging check safely")
        return 1

    print("DONE: read-only staging diagnosis. HTTP 502 can indicate a staged")
    print("form/timeout issue and is not evidence of successful login.")
    print("No account credentials supplied. No code deployed or tokens exchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
