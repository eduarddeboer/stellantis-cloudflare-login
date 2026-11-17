#!/usr/bin/env python3
"""Build and verify a local, deterministic HACS integration ZIP. Never publishes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "stellantis_vehicles"
DEFAULT_DEST = ROOT / "dist" / "stellantis_vehicles.zip"
REQUIRED = {"__init__.py", "manifest.json", "worker_oauth_client.py", "config_flow.py", "translations/en.json"}


def build(dest: Path) -> tuple[int, int]:
    metadata = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    if metadata.get("zip_release") is not True or metadata.get("filename") != "stellantis_vehicles.zip":
        raise ValueError("HACS release settings do not match stellantis_vehicles.zip")
    if manifest.get("domain") != "stellantis_vehicles" or not manifest.get("version"):
        raise ValueError("Invalid HA integration domain or missing version")

    files = []
    for file in COMPONENT.rglob("*"):
        if file.is_symlink():
            raise ValueError("No symlinks allowed in HACS release")
        if not file.is_file():
            continue
        rel = file.relative_to(COMPONENT)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts) or file.suffix == ".pyc":
            continue
        if file.suffix in {".key", ".pem", ".p12"} or rel.name in {"secrets.yaml", "configuration.yaml", ".env"}:
            raise ValueError("Secret-like file in integration tree")
        files.append((rel.as_posix(), file))
    names = {name for name, _ in files}
    missing = REQUIRED - names
    if missing:
        raise ValueError(f"Required integration files missing: {sorted(missing)}")
    if any(name.startswith("custom_components/") or name.startswith("worker/") for name in names):
        raise ValueError("ZIP files must be relative to the integration root")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(files):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(dest) as archive:
        actual = set(archive.namelist())
        if archive.testzip() is not None or actual != names:
            raise ValueError("ZIP validation failed")
        if json.loads(archive.read("manifest.json"))["version"] != manifest["version"]:
            raise ValueError("Wrong integration version inside ZIP")
    return len(names), dest.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()
    count, size = build(args.out)
    print(f"VALID: {args.out} ({count} integration files, {size} bytes); not published")


if __name__ == "__main__":
    main()
