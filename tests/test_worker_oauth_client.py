"""Offline tests for the existing single Home Assistant Worker OAuth client."""
from __future__ import annotations

import asyncio
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "stellantis_vehicles" / "worker_oauth_client.py"
spec = importlib.util.spec_from_file_location("stellantis_worker_client", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ENDPOINT = "https://testworker.example.workers.dev/"
API_KEY = "abcdefghijklmnopqrstuvwxyz123456"


class FakeResponse:
    def __init__(self, status, data):
        self.status, self.data = status, data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self.data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class WorkerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_code_obtained_only_from_explicit_owned_worker(self):
        session = FakeSession(FakeResponse(200, {"code": "not-a-real-code"}))
        code = await module.get_code_from_worker(
            session, email="example@example.invalid", password="example-not-real",
            authorize_url="https://example.invalid/am/oauth2/authorize",
            api_key=API_KEY, worker_url=ENDPOINT, confirmed=True,
        )
        self.assertEqual(code, "not-a-real-code")
        self.assertEqual(len(session.calls), 1)
        args, kwargs = session.calls[0]
        self.assertEqual(args, (ENDPOINT,))
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {API_KEY}")
        self.assertEqual(kwargs["json"]["password"], "example-not-real")

    async def test_unconfirmed_worker_never_receives_credentials(self):
        session = FakeSession(FakeResponse(200, {"code": "unused"}))
        with self.assertRaises(module.WorkerOAuthError):
            await module.get_code_from_worker(
                session, email="example@example.invalid", password="secret-not-real",
                authorize_url="https://example.invalid", api_key=API_KEY,
                worker_url=ENDPOINT, confirmed=False,
            )
        self.assertEqual(session.calls, [])

    async def test_unauthorized_and_malformed_responses_fail_closed(self):
        for status, data in [(401, {}), (302, {}), (200, {"code": ""}), (200, ["code"]), (200, {"message": "secret-not-real"})]:
            session = FakeSession(FakeResponse(status, data))
            with self.assertRaises(module.WorkerOAuthError) as ctx:
                await module.get_code_from_worker(
                    session, email="example@example.invalid", password="secret-not-real",
                    authorize_url="https://example.invalid", api_key=API_KEY,
                    worker_url=ENDPOINT, confirmed=True,
                )
            self.assertNotIn("secret-not-real", str(ctx.exception))
            self.assertNotIn("example@example.invalid", str(ctx.exception))

    async def test_worker_url_rejects_untrusted_origin(self):
        for url in ["http://testworker.example.workers.dev/",
                    "https://testworker.example.workers.dev.evil.invalid/",
                    "https://testworker.example.workers.dev/anything",
                    "https://testworker.example.workers.dev/?code=bad",
                    "https://user:password@testworker.example.workers.dev/",
                    "https://testworker.example.workers.dev:8443/"]:
            self.assertIsNone(module.normalized_worker_url(url), url)


class ControlOwnershipTests(unittest.TestCase):
    def test_ha_remote_login_has_no_legacy_http_post(self):
        path = ROOT / "custom_components/stellantis_vehicles/stellantis.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owner = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "StellantisOauth")
        get_code = next(f for f in owner.body if isinstance(f, ast.AsyncFunctionDef) and f.name == "get_oauth_code")
        calls = {n.func.attr for n in ast.walk(get_code) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("get_oauth_url", calls)
        self.assertNotIn("make_http_request", calls)
        self.assertIn("get_code_from_worker", {n.func.id for n in ast.walk(get_code) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})

    def test_no_default_third_party_worker(self):
        constants = (ROOT / "custom_components/stellantis_vehicles/const.py").read_text(encoding="utf-8")
        self.assertNotIn("onrender.com", constants)
        flow = (ROOT / "custom_components/stellantis_vehicles/config_flow.py").read_text(encoding="utf-8")
        self.assertIn("vol.Required(FIELD_OAUTH_CODE_URL)", flow)

    def test_all_localized_remote_forms_require_owned_worker(self):
        import json
        translations = ROOT / "custom_components/stellantis_vehicles/translations"
        for file in translations.glob("*.json"):
            data = json.loads(file.read_text(encoding="utf-8"))
            remote = data.get("config", {}).get("step", {}).get("oauth_remote")
            if remote is None:
                continue
            with self.subTest(locale=file.stem):
                self.assertNotIn("oauth_remote_link", remote.get("description", ""))
                self.assertIn("oauth_code_url", remote.get("data", {}))


if __name__ == "__main__":
    unittest.main()
