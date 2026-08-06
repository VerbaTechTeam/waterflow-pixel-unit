#!/usr/bin/env python3
"""Build OTA release artifacts: copy files, stamp version, emit manifest.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paths relative to repo root. ota.py is included when present (added in OTA stage).
ROOT_FILES = [
    "main.py",
    "myhttp.py",
    "auth.py",
    "utils.py",
    "waterflowdriver.py",
    "waterflowpixel.py",
    "neopixel.py",
    "ktime.py",
    "version.py",
    "ota.py",
]

LIB_GLOBS = [
    "lib/phew/**/*.py",
    "lib/hashlib/**/*.py",
    "lib/random.py",
]


def path_to_asset(rel_path: str) -> str:
    return rel_path.replace("/", "__").replace("\\", "__")


def version_py_content(version: str) -> str:
    return f'__version__ = "{version}"\n'


def collect_ota_paths() -> list[str]:
    paths: list[str] = []
    missing: list[str] = []

    for name in ROOT_FILES:
        path = ROOT / name
        if name == "ota.py" and not path.is_file():
            continue
        if name == "version.py":
            paths.append(name)
            continue
        if not path.is_file():
            missing.append(name)
            continue
        paths.append(name.replace("\\", "/"))

    for pattern in LIB_GLOBS:
        matched = sorted(ROOT.glob(pattern))
        if not matched and "*" not in pattern:
            missing.append(pattern)
        for path in matched:
            if not path.is_file():
                continue
            if "dist-info" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel not in paths:
                paths.append(rel)

    if missing:
        print("Missing required files:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        sys.exit(1)

    return sorted(paths)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build(version: str, out_dir: Path, update_source_version: bool) -> None:
    if update_source_version:
        (ROOT / "version.py").write_text(version_py_content(version), encoding="utf-8")

    paths = collect_ota_paths()

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    files_meta = []
    for rel in paths:
        asset = path_to_asset(rel)
        dst = out_dir / asset
        dst.parent.mkdir(parents=True, exist_ok=True)

        if rel == "version.py":
            data = version_py_content(version).encode("utf-8")
            dst.write_bytes(data)
            digest = sha256_bytes(data)
        else:
            src = ROOT / rel
            shutil.copy2(src, dst)
            digest = sha256_file(dst)

        files_meta.append(
            {
                "path": rel,
                "asset": asset,
                "sha256": digest,
            }
        )

    manifest = {
        "version": version,
        "files": files_meta,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(files_meta)} files + manifest.json -> {out_dir}")


def normalize_version(raw: str) -> str:
    version = raw.strip()
    if version.startswith("v") or version.startswith("V"):
        version = version[1:]
    if not version:
        print("Version must not be empty", file=sys.stderr)
        sys.exit(1)
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Waterflow Pixel Unit OTA release dist")
    parser.add_argument("--version", required=True, help="Release version (e.g. 1.2.0 or v1.2.0)")
    parser.add_argument("--out", default="dist", help="Output directory (default: dist)")
    parser.add_argument(
        "--update-source-version",
        action="store_true",
        help="Also write version.py in the repository root (use in CD)",
    )
    args = parser.parse_args()

    version = normalize_version(args.version)
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    build(version, out_dir, update_source_version=args.update_source_version)


if __name__ == "__main__":
    main()
