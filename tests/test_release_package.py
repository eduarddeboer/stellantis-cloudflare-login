"""Credential-free assertions for the HACS integration artifact."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_release_zip.py"
spec = importlib.util.spec_from_file_location("build_release_zip", BUILDER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleasePackageTests(unittest.TestCase):
    def test_hacs_archive_root_and_contents(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "stellantis_vehicles.zip"
            count, size = module.build(dest)
            self.assertGreater(count, 10)
            self.assertGreater(size, 1000)
            with zipfile.ZipFile(dest) as archive:
                names = archive.namelist()
                self.assertEqual(names, sorted(names))
                self.assertEqual(len(names), len(set(names)))
                self.assertIn("__init__.py", names)
                self.assertIn("manifest.json", names)
                self.assertIn("worker_oauth_client.py", names)
                self.assertIn("translations/nl.json", names)
                self.assertNotIn("custom_components/stellantis_vehicles/manifest.json", names)
                self.assertFalse(any(name.startswith("worker/") for name in names))
                self.assertFalse(any("node_modules" in name or "__pycache__" in name for name in names))
                self.assertIsNone(archive.testzip())

    def test_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "a.zip", Path(td) / "b.zip"
            module.build(a)
            module.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
