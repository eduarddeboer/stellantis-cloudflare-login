"""Offline regression tests for credential-free staging diagnostics.

Never performs a network request or reads a real API key.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_staging_readonly.py"
spec = importlib.util.spec_from_file_location("stellantis_staging_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.data[:limit]


class StagingReadOnlyTests(unittest.TestCase):
    def test_public_oauth_url_comes_from_existing_nl_settings(self):
        url = module.public_authorize_url()
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "idpcvs.peugeot.com")
        self.assertEqual(parsed.path, "/am/oauth2/authorize")
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["redirect_uri"], ["mymap://oauth2redirect/nl"])
        self.assertEqual(params["locale"], ["nl-NL"])
        self.assertIn("client_id", params)
        self.assertNotIn("client_secret", url)
        self.assertNotIn("password", url)

    def test_worker_url_reuses_canonical_trust_policy(self):
        self.assertEqual(
            module.normalized_worker_url("https://stellantis-staging.ownaccount.workers.dev"),
            "https://stellantis-staging.ownaccount.workers.dev/",
        )
        for bad in (
            "http://stellantis-staging.ownaccount.workers.dev",
            "https://workers.dev",
            "https://other.example.invalid",
            "https://stellantis-staging.ownaccount.workers.dev.evil.test",
            "https://stellantis-staging.ownaccount.workers.dev/login",
            "https://user:pass@stellantis-staging.ownaccount.workers.dev",
        ):
            with self.subTest(url=bad):
                self.assertIsNone(module.normalized_worker_url(bad))

    def test_never_calls_any_credential_bearing_or_unknown_endpoint(self):
        with patch.object(module, "build_opener") as opener:
            for path in ("/", "/login", "/token", "/browser-check", "/health"):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(ValueError, "Only read-only"):
                        module.inspect(
                            "https://own.account.workers.dev/", "FAKE-KEY", path,
                            "https://idpcvs.peugeot.com/am/oauth2/authorize",
                        )
            opener.assert_not_called()

    def test_read_only_http_body_never_contains_account_credentials(self):
        calls = []

        class FakeOpener:
            def open(self, request, timeout):
                calls.append((request, timeout))
                return FakeResponse({"allowed": True})

        with patch.object(module, "build_opener", return_value=FakeOpener()) as factory:
            status, data = module.inspect(
                "https://own.account.workers.dev/", "FAKE-KEY",
                "/validate", module.public_authorize_url(),
            )
        self.assertEqual((status, data), (200, {"allowed": True}))
        factory.assert_called_once_with(module.NoRedirect)
        req, timeout = calls[0]
        self.assertEqual(timeout, 100)
        self.assertEqual(req.get_method(), "POST")
        self.assertTrue(req.full_url.endswith("/validate"))
        self.assertEqual(req.get_header("Authorization"), "Bearer FAKE-KEY")
        payload = json.loads(req.data)
        # The public OAuth scope legitimately contains the word "email".
        # Check request JSON fields, not substrings inside the OAuth URL.
        self.assertEqual(payload, {"url": module.public_authorize_url()})
        for credential_field in ("email", "password", "username", "api_key", "access_token"):
            self.assertNotIn(credential_field, payload)
        self.assertNotIn("FAKE-KEY", payload["url"])

    def test_redirect_handler_refuses_all_redirects(self):
        handler = module.NoRedirect()
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.assertIsNone(handler.redirect_request(
                    None, None, status, "moved", {}, "https://evil.test/",
                ))

    def test_http_redirect_status_is_not_followed_or_treated_as_success(self):
        redirect_errors = []

        class FakeOpener:
            def open(self, request, timeout):
                error = HTTPError(
                    request.full_url, 302, "Moved", {},
                    io.BytesIO(b'{"allowed":false}'),
                )
                redirect_errors.append(error)
                raise error

        with patch.object(module, "build_opener", return_value=FakeOpener()):
            status, data = module.inspect(
                "https://own.account.workers.dev/", "FAKE-KEY",
                "/validate", module.public_authorize_url(),
            )
        self.assertEqual(status, 302)
        self.assertEqual(data, {"allowed": False})
        self.assertEqual(len(redirect_errors), 1)
        self.assertTrue(redirect_errors[0].closed)

    def test_report_never_echoes_untrusted_urls_secrets_or_provider_text(self):
        data = {
            "message": "PASSWORD-CODE-SECRET",
            "stage": "login_password_field",
            "reason": "timeout",
            "oauth_url": "https://not-allowed.example/?code=SECRET",
            "public_page": {
                "page_category": "peugeot_identity",
                "document_kind": "html",
                "unsafe": "PASSWORD-CODE-SECRET",
            },
            "form_visibility": {
                "main_email_visible": True,
                "main_password_visible": False,
                "unsafe": "PASSWORD-CODE-SECRET",
            },
        }
        result = "\n".join(module.safe_report(502, data))
        self.assertIn("HTTP 502", result)
        self.assertIn("peugeot_identity", result)
        self.assertIn("main_email_visible: True", result)
        self.assertNotIn("SECRET", result)
        self.assertNotIn("not-allowed.example", result)


if __name__ == "__main__":
    unittest.main()
