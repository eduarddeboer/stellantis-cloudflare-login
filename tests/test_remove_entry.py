"""Offline tests of the canonical Stellantis config-entry cleanup owner.

Executes the actual async_remove_entry and _device_vins function bodies from
custom_components/stellantis_vehicles/__init__.py with in-memory Home Assistant
stubs and a disposable tempfile tree. No network, real accounts, or HA imports.
"""

from __future__ import annotations

import ast
import copy
import logging
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "custom_components" / "stellantis_vehicles" / "__init__.py"


class RemovalOwnerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tree = ast.parse(OWNER.read_text(encoding="utf-8"), filename=str(OWNER))
        names = ("_device_vins", "async_remove_entry")
        nodes = [copy.deepcopy(node) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
        if [node.name for node in nodes] != list(names):
            raise AssertionError("Canonical removal functions missing or reordered")
        dr = SimpleNamespace(
            DeviceEntry=object,
            async_get=lambda hass: hass.device_registry,
            async_entries_for_config_entry=lambda registry, entry_id: registry.get(entry_id, []),
        )
        cls.owner_globals = {
            "dr": dr, "os": os, "shutil": shutil,
            "HomeAssistant": object, "ConfigEntry": object,
            "DOMAIN": "stellantis_vehicles", "SOURCE_IGNORE": "ignore",
            "OTP_FILENAME": "{#customer_id#}_otp.pickle",
            "INTEGRATION_VERSION": 20261003,
            "_LOGGER": logging.getLogger("stellantis_test_removal"),
            "vehicle_removed_issue_id": lambda vin: f"vehicle_removed_{vin}",
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(OWNER), "exec"), cls.owner_globals)
        cls.remove_entry = staticmethod(cls.owner_globals["async_remove_entry"])

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory(prefix="stellantis-removal-test-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.deleted_issues = []
        self.removed_urls = []
        self.executor_jobs = 0
        self.entries = []
        self.registry = {}
        self.owner_globals["issue_registry"] = SimpleNamespace(
            async_delete_issue=lambda hass, domain, issue: self.deleted_issues.append((domain, issue))
        )
        self.owner_globals["remove_extra_js_url"] = lambda hass, url: self.removed_urls.append(url)
        self.hass = SimpleNamespace(
            config=SimpleNamespace(path=lambda *parts: str(self.root.joinpath(*parts))),
            config_entries=SimpleNamespace(async_entries=lambda domain: list(self.entries)),
            device_registry=self.registry,
            async_add_executor_job=self._run_executor,
        )

    async def _run_executor(self, function):
        self.executor_jobs += 1
        function()

    def entry(self, entry_id, customer_id=None, *, source="user", vin=None):
        data = {} if customer_id is None else {"customer_id": customer_id}
        config = SimpleNamespace(entry_id=entry_id, data=data, source=source)
        self.entries.append(config)
        self.registry[entry_id] = [] if not vin else [SimpleNamespace(identifiers={
            ("stellantis_vehicles", vin), ("another_integration", "unrelated")
        })]
        return config

    def file(self, relative, content=b"fake local fixture"):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    async def test_last_entry_removes_otp_and_vehicle_images_but_not_other_integration(self):
        vin = "TESTVIN1234567890"
        config = self.entry("entry-1", "MN-FICTIVE1", vin=vin)
        otp = self.file(".storage/stellantis_vehicles/MN-FICTIVE1_otp.pickle")
        image = self.file(f"www/stellantis_vehicles/MN-FICTIVE1/{vin}.png")
        unrelated = self.file("www/another_integration/keep.txt")
        unrelated_store = self.file(".storage/another_integration/keep.txt")
        await self.remove_entry(self.hass, config)
        self.assertFalse(otp.exists())
        self.assertFalse(image.exists())
        self.assertFalse((self.root / "www/stellantis_vehicles").exists())
        self.assertFalse((self.root / ".storage/stellantis_vehicles").exists())
        self.assertTrue(unrelated.exists())
        self.assertTrue(unrelated_store.exists())
        self.assertEqual(self.deleted_issues, [("stellantis_vehicles", f"vehicle_removed_{vin}")])
        self.assertEqual(len(self.removed_urls), 1)
        self.assertEqual(self.executor_jobs, 1)

    async def test_shared_account_keeps_otp_and_other_entry_image(self):
        vin_a = "TESTVIN1234567890"
        vin_b = "TESTVIN2345678901"
        own = self.entry("entry-a", "MN-SHARED", vin=vin_a)
        self.entry("entry-b", "MN-SHARED", vin=vin_b)
        otp = self.file(".storage/stellantis_vehicles/MN-SHARED_otp.pickle")
        first = self.file(f"www/stellantis_vehicles/MN-SHARED/{vin_a}.png")
        second = self.file(f"www/stellantis_vehicles/MN-SHARED/{vin_b}.png")
        await self.remove_entry(self.hass, own)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertTrue(otp.exists())
        self.assertTrue((self.root / "www/stellantis_vehicles/MN-SHARED").exists())
        self.assertEqual(self.removed_urls, [], "Other active config entry still uses the card")

    async def test_other_account_resources_are_left_untouched(self):
        vin_a = "TESTVIN1234567890"
        own = self.entry("entry-a", "MN-ACCOUNT-A", vin=vin_a)
        self.entry("entry-b", "MN-ACCOUNT-B")
        own_otp = self.file(".storage/stellantis_vehicles/MN-ACCOUNT-A_otp.pickle")
        other_otp = self.file(".storage/stellantis_vehicles/MN-ACCOUNT-B_otp.pickle")
        other_img = self.file("www/stellantis_vehicles/MN-ACCOUNT-B/other.png")
        self.file(f"www/stellantis_vehicles/MN-ACCOUNT-A/{vin_a}.png")
        await self.remove_entry(self.hass, own)
        self.assertFalse(own_otp.exists())
        self.assertTrue(other_otp.exists())
        self.assertTrue(other_img.exists())
        self.assertEqual(self.removed_urls, [])

    async def test_unconfigured_entry_makes_no_filesystem_changes(self):
        config = self.entry("entry-empty")
        other = self.file("www/stellantis_vehicles/MN-PRESERVE/picture.png")
        await self.remove_entry(self.hass, config)
        self.assertTrue(other.exists())
        self.assertEqual(self.executor_jobs, 0)
        self.assertEqual(len(self.removed_urls), 1)

    async def test_last_entry_cleans_orphan_images_only_within_its_own_folder(self):
        config = self.entry("entry-last", "MN-STALe")
        orphan = self.file("www/stellantis_vehicles/MN-STALe/orphan.png")
        other = self.file("www/stellantis_vehicles/MN-OTHER/untouched.png")
        await self.remove_entry(self.hass, config)
        self.assertFalse(orphan.exists())
        self.assertTrue(other.exists())

    async def test_ignored_entries_do_not_block_frontend_cleanup(self):
        config = self.entry("entry-real", "MN-REAL")
        self.entry("entry-ignored", "MN-IGNORED", source="ignore")
        await self.remove_entry(self.hass, config)
        self.assertEqual(len(self.removed_urls), 1)

    async def test_storage_directory_with_other_artifacts_is_preserved(self):
        config = self.entry("entry-real", "MN-REAL")
        otp = self.file(".storage/stellantis_vehicles/MN-REAL_otp.pickle")
        preserved = self.file(".storage/stellantis_vehicles/MN-OTHER_otp.pickle")
        await self.remove_entry(self.hass, config)
        self.assertFalse(otp.exists())
        self.assertTrue(preserved.exists())
        self.assertTrue(preserved.parent.exists())


if __name__ == "__main__":
    unittest.main()
