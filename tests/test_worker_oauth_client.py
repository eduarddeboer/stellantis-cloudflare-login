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


    async def test_http_401_is_typed_key_rejection_not_generic_worker_failure(self):
        session = FakeSession(FakeResponse(401, {"message": "untrusted-worker-text"}))
        with self.assertRaises(module.WorkerOAuthKeyRejected) as ctx:
            await module.get_code_from_worker(
                session, email="example@example.invalid", password="secret-not-real",
                authorize_url="https://example.invalid", api_key=API_KEY,
                worker_url=ENDPOINT, confirmed=True,
            )
        self.assertNotIn("untrusted-worker-text", str(ctx.exception))

    async def test_other_http_failures_do_not_masquerade_as_invalid_key(self):
        session = FakeSession(FakeResponse(403, {"message": "irrelevant"}))
        with self.assertRaises(module.WorkerOAuthError) as ctx:
            await module.get_code_from_worker(
                session, email="example@example.invalid", password="secret-not-real",
                authorize_url="https://example.invalid", api_key=API_KEY,
                worker_url=ENDPOINT, confirmed=True,
            )
        self.assertNotIsInstance(ctx.exception, module.WorkerOAuthKeyRejected)


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
            "WorkerOAuthKeyRejected": module.WorkerOAuthKeyRejected,
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

    async def test_worker_http_401_reports_api_key_field_without_secret_leak(self):
        flow = self.new_flow()
        async def refused(*args, **kwargs):
            raise module.WorkerOAuthKeyRejected("Worker API key rejected (HTTP 401)")
        flow.stellantis.get_oauth_code = refused
        result = await flow.async_step_oauth_remote(self.user_input(
            ENDPOINT, override_key="invalid-test-key-not-a-secret-123456"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"], {"oauth_worker_api_key": "worker_key_rejected"})
        self.assertEqual(result["data_schema"]["email"], "tester@example.invalid")
        self.assertEqual(result["data_schema"]["prefill"], ENDPOINT)
        self.assertNotIn("password", result["data_schema"])
        self.assertNotIn("oauth_worker_api_key", result["data_schema"])
        self.assertEqual(flow.stellantis.saved, [])

    async def test_worker_http_401_stays_on_form_for_reconfigure(self):
        flow = self.new_flow()
        flow.source = "reconfigure"
        async def refused(*args, **kwargs):
            raise module.WorkerOAuthKeyRejected("Worker API key rejected (HTTP 401)")
        flow.stellantis.get_oauth_code = refused
        result = await flow.async_step_oauth_remote(self.user_input(
            ENDPOINT, override_key="invalid-test-key-not-a-secret-123456"))
        self.assertEqual(result["step_id"], "oauth_remote")
        self.assertEqual(result["errors"], {"oauth_worker_api_key": "worker_key_rejected"})

    def test_key_rejected_has_dutch_and_english_translations(self):
        import json
        for locale in ("nl", "en"):
            path = ROOT / "custom_components" / "stellantis_vehicles" / "translations" / (locale + ".json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("worker_key_rejected", data["config"]["error"])

class OfflineOAuthChainTests(unittest.IsolatedAsyncioTestCase):
    """Use the actual OAuth flow owner with fake tokens; no HA or network imports."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import copy
        from datetime import datetime, timedelta
        from uuid import uuid4
        file = ROOT / "custom_components" / "stellantis_vehicles" / "config_flow.py"
        tree = ast.parse(file.read_text(encoding="utf-8"))
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "StellantisVehiclesConfigFlow")
        names = ("async_step_oauth_remote", "async_step_get_access_token")
        methods = [copy.deepcopy(n) for n in owner.body
                   if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
        if {m.name for m in methods} != set(names):
            raise AssertionError("Expected the canonical OAuth flow methods")
        for method in methods:
            method.decorator_list = []
        ns = {
            "CONF_EMAIL": "email", "CONF_PASSWORD": "password",
            "FIELD_OAUTH_CODE_URL": "oauth_code_url",
            "FIELD_OAUTH_WORKER_API_KEY": "oauth_worker_api_key",
            "FIELD_OAUTH_WORKER_TRUST": "oauth_worker_trust_confirm",
            "FIELD_OAUTH_MANUAL_MODE": "oauth_manual_mode",
            "FIELD_REMOTE_COMMANDS": "remote_commands",
            "SOURCE_RECONFIGURE": "reconfigure",
            "TRANSLATION_PLACEHOLDERS": {},
            "normalized_worker_url": module.normalized_worker_url,
            "WorkerOAuthKeyRejected": module.WorkerOAuthKeyRejected,
            "OAUTH_REMOTE_SCHEMA": lambda url=None, email=None: {"url": url, "email": email},
            "OTP_CONFIGURE_SCHEMA": lambda enabled=False: {"remote_commands_default": enabled},
            "get_datetime": lambda: datetime(2026, 11, 17, 12, 0, 0),
            "timedelta": timedelta, "uuid4": uuid4,
        }
        exec(compile(ast.fix_missing_locations(ast.Module(
            body=methods, type_ignores=[])), str(file), "exec"), ns)
        cls.remote = ns["async_step_oauth_remote"]
        cls.token = ns["async_step_get_access_token"]

    def fake_flow(self, *, existing_remote=False, source="user"):
        class FakeStellantis:
            def __init__(self):
                self.saved = []
                self.requests = []
            async def get_oauth_code(self, email, password, url, **kwargs):
                self.requests.append("worker_code")
                assert email == "tester@example.invalid"
                assert password == "fake-password-not-real"
                assert kwargs["worker_trust_confirm"] is True
                return {"code": "FAKE-CODE-NOT-REAL"}
            async def get_access_token(self):
                self.requests.append("token_exchange")
                assert {"oauth_code": "FAKE-CODE-NOT-REAL"} in self.saved
                return {"access_token": "FAKE-ACCESS-ONLY", "refresh_token": "FAKE-REFRESH-ONLY",
                        "expires_in": 3600}
            def save_config(self, config):
                self.saved.append(config)
            async def hass_notify(self, *args):
                self.requests.append("notify")

        class FakeFlow:
            def __init__(self, parent):
                self.source = source
                self.data = {"remote_commands": existing_remote}
                self.errors = {}
                self.stellantis = FakeStellantis()
                self.async_step_oauth_remote = type(parent).remote.__get__(self, FakeFlow)
                self.async_step_get_access_token = type(parent).token.__get__(self, FakeFlow)
            def async_show_form(self, **kwargs):
                return {"type": "form", **kwargs}
            def get_error_message(self, *_):
                return "fixed-error"
            def async_abort(self, **kwargs):
                return {"type": "abort", **kwargs}
            async def async_step_oauth_mode(self):
                return {"type": "oauth_mode"}
            async def async_step_otp(self):
                return {"type": "otp"}
            async def async_step_options(self):
                return {"type": "options"}
            async def async_step_final(self):
                return {"type": "final"}
        return FakeFlow(self)

    async def test_code_exchanged_and_tokens_saved_without_ui_exposure(self):
        flow = self.fake_flow()
        outcome = await flow.async_step_oauth_remote({
            "email": "tester@example.invalid", "password": "fake-password-not-real",
            "oauth_code_url": ENDPOINT, "oauth_worker_api_key": API_KEY,
            "oauth_worker_trust_confirm": True,
        })
        self.assertEqual(outcome["step_id"], "get_access_token")
        self.assertEqual(flow.stellantis.requests, ["worker_code", "token_exchange"])
        self.assertEqual(flow.stellantis.saved[0], {"oauth_code": "FAKE-CODE-NOT-REAL"})
        tokens = flow.data["oauth"]
        self.assertEqual(tokens["access_token"], "FAKE-ACCESS-ONLY")
        self.assertEqual(tokens["refresh_token"], "FAKE-REFRESH-ONLY")
        self.assertIn("2026-11-17T13:00:00", tokens["expires_in"])
        self.assertEqual(outcome["data_schema"]["remote_commands_default"], False)
        for secret in ("FAKE-CODE-NOT-REAL", "FAKE-ACCESS-ONLY", "FAKE-REFRESH-ONLY", API_KEY):
            self.assertNotIn(secret, repr(outcome))

    async def test_initial_configuration_keeps_remote_commands_disabled(self):
        flow = self.fake_flow()
        # This step is reached only after a successful Worker OAuth code step.
        flow.stellantis.save_config({"oauth_code": "FAKE-CODE-NOT-REAL"})
        result = await flow.async_step_get_access_token()
        self.assertEqual(result["step_id"], "get_access_token")
        next_step = await flow.async_step_get_access_token({"remote_commands": False})
        self.assertEqual(next_step, {"type": "options"})
        self.assertFalse(flow.data["remote_commands"])
        self.assertTrue(flow.data["customer_id"].startswith("MN-"))
        self.assertNotIn("otp", flow.stellantis.requests)

    async def test_reauth_preserves_existing_remote_commands_default(self):
        flow = self.fake_flow(existing_remote=True, source="reauth")
        flow.data["customer_id"] = "EXISTING-NO-REAL-ACCOUNT"
        # Reauth has the same prerequisite: a saved authorization code.
        flow.stellantis.save_config({"oauth_code": "FAKE-CODE-NOT-REAL"})
        outcome = await flow.async_step_get_access_token()
        self.assertTrue(outcome["data_schema"]["remote_commands_default"])
        result = await flow.async_step_get_access_token({"remote_commands": True})
        self.assertEqual(result, {"type": "otp"})
        self.assertEqual(flow.data["customer_id"], "EXISTING-NO-REAL-ACCOUNT")

    async def test_token_exchange_failure_never_persists_tokens(self):
        flow = self.fake_flow()
        async def unavailable():
            raise RuntimeError("simulated backend outage")
        flow.stellantis.get_access_token = unavailable
        result = await flow.async_step_get_access_token()
        self.assertEqual(result, {"type": "oauth_mode"})
        self.assertNotIn("oauth", flow.data)
        self.assertTrue(flow.errors)


class OfflineOAuthRefreshTests(unittest.IsolatedAsyncioTestCase):
    """Exercise canonical refresh methods with fake backends and no HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import copy
        from datetime import datetime, timedelta
        file = ROOT / "custom_components" / "stellantis_vehicles" / "stellantis.py"
        tree = ast.parse(file.read_text(encoding="utf-8"))
        names = {"refresh_oauth_token_request", "_refresh_oauth_token_request"}
        methods = []
        for owner in tree.body:
            if isinstance(owner, ast.ClassDef):
                methods.extend(copy.deepcopy(method) for method in owner.body
                               if isinstance(method, ast.AsyncFunctionDef)
                               and method.name in names)
        if {method.name for method in methods} != names:
            raise AssertionError("Expected canonical OAuth refresh owner methods")
        for method in methods:
            method.decorator_list = []
        class ConfigEntryAuthFailed(Exception):
            pass
        class CommunicationError(Exception):
            pass
        ns = {
            "asyncio": asyncio,
            "ConfigEntryAuthFailed": ConfigEntryAuthFailed,
            "CommunicationError": CommunicationError,
            "RateLimitException": Exception,
            "OAUTH_TOKEN_URL": "https://example.invalid/token",
            "OAUTH_REFRESH_TOKEN_QUERY_PARAMS": {"grant_type": "refresh_token"},
            "OAUTH_TOKEN_HEADERS": {"Authorization": "FAKE-HEADER"},
            "get_datetime": lambda: datetime(2026, 11, 17, 12, 0, 0),
            "timedelta": timedelta,
            "_log_http_exchange": lambda *args: None,
            "_LOGGER": type("Logger", (), {"debug": lambda *args: None})(),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(
            body=methods, type_ignores=[])), str(file), "exec"), ns)
        cls.refresh = ns["refresh_oauth_token_request"]
        cls.rotate = ns["_refresh_oauth_token_request"]

    def fake_owner(self):
        class Mask:
            def __init__(self):
                self.items = []
            def add_custom_value(self, val):
                self.items.append(val)
        class Fake:
            _shutting_down = False
            _oauth_rejected_refresh_token = None
            def __init__(self, parent):
                self._oauth_refresh_lock = asyncio.Lock()
                self._config = {"oauth": {"access_token": "OLD-ACCESS", "refresh_token": "OLD-REFRESH"}}
                self.logger_filter = Mask()
                self.http_calls = 0
                self.persisted = []
                self._refresh_oauth_token_request = type(parent).rotate.__get__(self, Fake)
                self.refresh_oauth_token_request = type(parent).refresh.__get__(self, Fake)
            def get_config(self, key):
                return self._config.get(key)
            def apply_query_params(self, url, params):
                assert url == "https://example.invalid/token"
                return "https://example.invalid/token?grant_type=refresh_token&refresh_token=OLD-REFRESH"
            def apply_dict_params(self, headers):
                return dict(headers)
            async def make_http_request(self, url, method, headers):
                self.http_calls += 1
                await asyncio.sleep(0)
                return {"access_token": "NEW-ACCESS", "refresh_token": "NEW-REFRESH", "expires_in": 3600}
            def save_config(self, values):
                self._config.update(values)
            def update_stored_config(self, key, values):
                self.persisted.append((key, values))
        return Fake(self)

    async def test_refresh_rotates_and_persists_both_tokens(self):
        instance = self.fake_owner()
        await instance.refresh_oauth_token_request()
        self.assertEqual(instance.http_calls, 1)
        self.assertEqual(instance.get_config("oauth")["access_token"], "NEW-ACCESS")
        self.assertEqual(instance.get_config("oauth")["refresh_token"], "NEW-REFRESH")
        self.assertEqual(instance.persisted[0][0], "oauth")
        self.assertEqual(instance.persisted[0][1], instance.get_config("oauth"))
        self.assertIn("OLD-REFRESH", instance.logger_filter.items)

    async def test_stale_refresh_and_simultaneous_refresh_do_not_duplicate(self):
        instance = self.fake_owner()
        await asyncio.gather(instance.refresh_oauth_token_request("OLD-ACCESS"),
                             instance.refresh_oauth_token_request("OLD-ACCESS"))
        self.assertEqual(instance.http_calls, 1)
        self.assertEqual(len(instance.persisted), 1)
        await instance.refresh_oauth_token_request("OLD-ACCESS")
        self.assertEqual(instance.http_calls, 1)

    async def test_missing_token_fields_never_persists_broken_refresh(self):
        instance = self.fake_owner()
        async def incomplete(*args):
            instance.http_calls += 1
            return {"access_token": "NEW-ACCESS", "expires_in": 3600}
        instance.make_http_request = incomplete
        with self.assertRaises(KeyError):
            await instance.refresh_oauth_token_request()
        self.assertEqual(instance.get_config("oauth")["refresh_token"], "OLD-REFRESH")
        self.assertEqual(instance.persisted, [])


if __name__ == "__main__":
    unittest.main()
