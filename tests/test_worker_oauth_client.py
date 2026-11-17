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



class ConfigFlowReauthTests(unittest.IsolatedAsyncioTestCase):
    """Execute the actual config-flow owner method with offline HA substitutes.

    Never import Home Assistant, launch a browser or perform an HTTP request.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import copy
        flow_path = ROOT / "custom_components/stellantis_vehicles/config_flow.py"
        tree = ast.parse(flow_path.read_text(encoding="utf-8"))
        owner = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == "StellantisVehiclesConfigFlow")
        method = next(node for node in owner.body
                      if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == "async_step_oauth_remote")
        standalone = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(method)], type_ignores=[]))
        namespace = {
            "FIELD_OAUTH_CODE_URL": "oauth_code_url",
            "FIELD_OAUTH_WORKER_API_KEY": "oauth_worker_api_key",
            "FIELD_OAUTH_WORKER_TRUST": "oauth_worker_trust_confirm",
            "CONF_EMAIL": "email",
            "CONF_PASSWORD": "password",
            "TRANSLATION_PLACEHOLDERS": {},
            "SOURCE_RECONFIGURE": "reconfigure",
            "OAUTH_REMOTE_SCHEMA": lambda old=None, email=None: {"prefill": old, "email": email},
            "normalized_worker_url": module.normalized_worker_url,
        }
        exec(compile(standalone, str(flow_path), "exec"), namespace)
        cls.handler = namespace["async_step_oauth_remote"]

    def new_flow(self, *, saved_url=None, saved_key=None):
        class FakeStellantis:
            def __init__(self):
                self.calls = []
                self.saved = []
            async def get_oauth_code(self, email, password, url, **kwargs):
                self.calls.append({"url": url, "key": kwargs.get("worker_api_key"),
                                   "confirmed": kwargs.get("worker_trust_confirm")})
                return {"code": "dummy-code-not-real"}
            def save_config(self, data):
                self.saved.append(data)
            async def hass_notify(self, *args):
                pass

        class FakeFlow:
            source = "user"
            def __init__(self):
                self.data = {}
                if saved_url is not None:
                    self.data["oauth_code_url"] = saved_url
                if saved_key is not None:
                    self.data["oauth_worker_api_key"] = saved_key
                self.stellantis = FakeStellantis()
                self.errors = {}
            def async_show_form(self, **kwargs):
                return {"result": "form", **kwargs}
            def get_error_message(self, key, message=None):
                return "fixed-error"
            async def async_step_oauth_mode(self):
                return {"result": "oauth_mode"}
            async def async_step_get_access_token(self):
                return {"result": "token_stage"}

        fake = FakeFlow()
        fake.async_step_oauth_remote = type(self).handler.__get__(fake, FakeFlow)
        return fake

    def user_input(self, url, *, override_key=None):
        supplied = {
            "email": "tester@example.invalid", "password": "NOT-A-REAL-PASSWORD",
            "oauth_code_url": url, "oauth_worker_trust_confirm": True,
        }
        if override_key is not None:
            supplied["oauth_worker_api_key"] = override_key
        return supplied

    async def test_canonical_worker_url_reuses_saved_key(self):
        """Same Worker entered without / or with host casing must retain key."""
        key = "this-is-a-test-worker-key-not-a-secret"
        flow = self.new_flow(saved_url="https://testworker.example.workers.dev/", saved_key=key)
        outcome = await flow.async_step_oauth_remote(self.user_input(
            "https://TESTWORKER.example.workers.dev"))
        self.assertEqual(outcome["result"], "token_stage")
        self.assertEqual(flow.stellantis.calls[0]["key"], key)
        self.assertEqual(flow.data["oauth_code_url"], "https://testworker.example.workers.dev/")

    async def test_exact_worker_url_keeps_key_normal_behavior(self):
        key = "this-is-a-test-worker-key-not-a-secret"
        url = "https://testworker.example.workers.dev/"
        flow = self.new_flow(saved_url=url, saved_key=key)
        await flow.async_step_oauth_remote(self.user_input(url))
        self.assertEqual(flow.stellantis.calls[0]["key"], key)

    async def test_different_worker_must_not_reuse_key(self):
        flow = self.new_flow(saved_url="https://first.example.workers.dev/",
                             saved_key="existing-secret-not-real")
        result = await flow.async_step_oauth_remote(self.user_input("https://second.example.workers.dev/"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"], {"oauth_worker_api_key": "worker_key_required"})
        self.assertEqual(flow.stellantis.calls, [])

    async def test_explicit_key_for_new_worker_is_respected(self):
        flow = self.new_flow(saved_url="https://first.example.workers.dev/",
                             saved_key="existing-secret-not-real")
        await flow.async_step_oauth_remote(self.user_input(
            "https://second.example.workers.dev/", override_key="NEW-KEY-NOT-REAL"))
        self.assertEqual(flow.stellantis.calls[0]["key"], "NEW-KEY-NOT-REAL")

    async def test_invalid_url_shows_form_without_oauth_request(self):
        flow = self.new_flow()
        result = await flow.async_step_oauth_remote(self.user_input("https://invalid.example/"))
        self.assertEqual(result["result"], "form")
        self.assertEqual(result["errors"], {"oauth_code_url": "invalid_worker_url"})
        self.assertEqual(flow.stellantis.calls, [])
        self.assertEqual(flow.stellantis.saved, [])

    async def test_missing_consent_returns_to_same_step_without_oauth_call(self):
        flow = self.new_flow()
        values = self.user_input("https://testworker.example.workers.dev/",
                                 override_key="test-key-not-real-123456789012")
        values["oauth_worker_trust_confirm"] = False
        result = await flow.async_step_oauth_remote(values)
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"],
                         {"oauth_worker_trust_confirm": "worker_owner_confirmation_required"})
        self.assertEqual(result["data_schema"]["email"], "tester@example.invalid")
        self.assertEqual(result["data_schema"]["prefill"], values["oauth_code_url"])
        self.assertNotIn("password", result["data_schema"])
        self.assertNotIn("oauth_worker_api_key", result["data_schema"])
        self.assertEqual(flow.stellantis.calls, [])

    async def test_missing_key_returns_same_step_without_oauth_call(self):
        flow = self.new_flow()
        result = await flow.async_step_oauth_remote(
            self.user_input("https://testworker.example.workers.dev/"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"], {"oauth_worker_api_key": "worker_key_required"})
        self.assertEqual(flow.stellantis.calls, [])

    async def test_missing_both_constraints_reports_both(self):
        flow = self.new_flow()
        values = self.user_input("https://testworker.example.workers.dev/")
        values["oauth_worker_trust_confirm"] = False
        result = await flow.async_step_oauth_remote(values)
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(set(result["errors"]),
                         {"oauth_worker_api_key", "oauth_worker_trust_confirm"})
        self.assertEqual(flow.stellantis.calls, [])

    async def test_invalid_url_keeps_entered_nonsecret_values(self):
        flow = self.new_flow()
        result = await flow.async_step_oauth_remote(
            self.user_input("https://invalid.example/"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["data_schema"]["email"], "tester@example.invalid")
        self.assertEqual(result["data_schema"]["prefill"], "https://invalid.example/")
        self.assertEqual(flow.stellantis.calls, [])

    async def test_oauth_failure_stays_on_same_step_without_echoing_secrets(self):
        flow = self.new_flow()
        async def refused(*args, **kwargs):
            raise RuntimeError("provider error: not-for-UI")
        flow.stellantis.get_oauth_code = refused
        result = await flow.async_step_oauth_remote(self.user_input(
            "https://testworker.example.workers.dev/",
            override_key="test-key-not-real-123456789012"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"], {"base": "get_oauth_code"})
        self.assertEqual(result["data_schema"]["email"], "tester@example.invalid")
        self.assertNotIn("password", result["data_schema"])
        self.assertNotIn("oauth_worker_api_key", result["data_schema"])


if __name__ == "__main__":
    unittest.main()
