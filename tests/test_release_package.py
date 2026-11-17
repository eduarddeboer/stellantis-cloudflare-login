"""Credential-free assertions for the HACS integration artifact."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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


    def test_release_tag_identical_to_manifest_version_builds_zip(self):
        with tempfile.TemporaryDirectory() as td:
            import json
            version = json.loads(
                (ROOT / "custom_components" / "stellantis_vehicles" / "manifest.json").read_text(encoding="utf-8")
            )["version"]
            dest = Path(td) / "stellantis_vehicles.zip"
            count, _ = module.build(dest, release_tag=version)
            self.assertGreater(count, 10)
            with zipfile.ZipFile(dest) as archive:
                self.assertEqual(
                    json.loads(archive.read("manifest.json"))["version"], version
                )

    def test_wrong_release_tag_fails_before_any_zip_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "stellantis_vehicles.zip"
            with self.assertRaisesRegex(ValueError, "must exactly match"):
                module.build(dest, release_tag="9999.99.99-nonexistent")
            self.assertFalse(dest.exists())

    def test_tag_with_v_prefix_is_not_silently_normalized(self):
        with tempfile.TemporaryDirectory() as td:
            import json
            version = json.loads(
                (ROOT / "custom_components" / "stellantis_vehicles" / "manifest.json").read_text(encoding="utf-8")
            )["version"]
            dest = Path(td) / "stellantis_vehicles.zip"
            with self.assertRaisesRegex(ValueError, "must exactly match"):
                module.build(dest, release_tag=f"v{version}")
            self.assertFalse(dest.exists())


    def test_release_cli_prints_digest_of_exact_archive_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = json.loads(
                (ROOT / "custom_components" / "stellantis_vehicles" / "manifest.json").read_text(encoding="utf-8")
            )
            dest = Path(td) / "stellantis_vehicles.zip"
            result = subprocess.run(
                [
                    sys.executable, str(BUILDER),
                    "--out", str(dest),
                    "--release-tag", manifest["version"],
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("VALID:", result.stdout)
            expected = hashlib.sha256(dest.read_bytes()).hexdigest()
            self.assertIn(f"SHA256: {expected}", result.stdout)
            self.assertEqual(result.stdout.count("SHA256:"), 1)


    def test_release_source_accepts_matching_clean_commit(self):
        expected = "a" * 40
        replies = [
            subprocess.CompletedProcess([], 0, stdout=expected + "\n"),
            subprocess.CompletedProcess([], 0, stdout=""),
        ]
        with patch.object(module.subprocess, "run", side_effect=replies) as runner:
            self.assertEqual(module.verify_release_source(expected), expected)
        self.assertEqual(runner.call_count, 2)
        for call in runner.call_args_list:
            self.assertEqual(call.kwargs["cwd"], ROOT)
            self.assertTrue(call.kwargs["check"])

    def test_release_source_rejects_wrong_commit(self):
        expected = "a" * 40
        actual = "b" * 40
        with patch.object(
            module.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, stdout=actual + "\n"),
        ):
            with self.assertRaisesRegex(ValueError, "HEAD does not match"):
                module.verify_release_source(expected)

    def test_release_source_rejects_dirty_checkout(self):
        expected = "a" * 40
        replies = [
            subprocess.CompletedProcess([], 0, stdout=expected + "\n"),
            subprocess.CompletedProcess([], 0, stdout=" M custom_components/stellantis_vehicles/config_flow.py\n"),
        ]
        with patch.object(module.subprocess, "run", side_effect=replies):
            with self.assertRaisesRegex(ValueError, "not clean"):
                module.verify_release_source(expected)

    def test_release_source_rejects_abbreviated_or_malformed_sha_without_git(self):
        with patch.object(module.subprocess, "run") as runner:
            for invalid in ("abc1234", "not-a-commit", "g" * 40, ""):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "full 40-character"):
                        module.verify_release_source(invalid)
            runner.assert_not_called()

    def test_release_source_fails_closed_if_git_unavailable(self):
        with patch.object(module.subprocess, "run", side_effect=OSError("git unavailable")):
            with self.assertRaisesRegex(ValueError, "Cannot verify"):
                module.verify_release_source("a" * 40)


    def test_release_cli_rejects_mismatched_expected_commit_without_zip(self):
        with tempfile.TemporaryDirectory() as td:
            version = json.loads(
                (ROOT / "custom_components" / "stellantis_vehicles" / "manifest.json").read_text(encoding="utf-8")
            )["version"]
            dest = Path(td) / "stellantis_vehicles.zip"
            result = subprocess.run(
                [
                    sys.executable, str(BUILDER), "--out", str(dest),
                    "--release-tag", version, "--expected-commit", "0" * 40,
                ],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("HEAD does not match", result.stderr)
            self.assertFalse(dest.exists())

    def test_release_cli_requires_tag_when_expected_commit_is_supplied(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "stellantis_vehicles.zip"
            result = subprocess.run(
                [sys.executable, str(BUILDER), "--out", str(dest),
                 "--expected-commit", "0" * 40],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--expected-commit requires --release-tag", result.stderr)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
