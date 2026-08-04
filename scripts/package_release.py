#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_dist import EXPECTED_OTF_FILENAMES


DEFAULT_VERSION = "0.1.1"
RELEASE_ROOT_FILES = ("specimen.pdf", "README.md", "LICENSE", "NOTICE")


def normalize_version(version: str) -> str:
    normalized = version.removeprefix("v").strip()
    if not normalized:
        raise ValueError("Version must not be empty")
    return normalized


def release_zip_name(version: str) -> str:
    return f"SNUAppendard-v{normalize_version(version)}.zip"


def release_note_name(version: str) -> str:
    return f"SNUAppendard-v{normalize_version(version)}-release-notes.md"


def checksum_name(version: str) -> str:
    return f"{release_zip_name(version)}.sha256"


def expected_release_entries() -> list[str]:
    return [f"otf/{name}" for name in EXPECTED_OTF_FILENAMES] + list(RELEASE_ROOT_FILES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify a GitHub release package for SNU Appendard."
    )
    parser.add_argument(
        "--version",
        default=os.environ.get("VERSION", DEFAULT_VERSION),
        help="Release version, with or without a leading v.",
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("PYTHON", sys.executable),
        help="Python executable to pass to make.",
    )
    parser.add_argument("--make", default=os.environ.get("MAKE", "make"))
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--release-note", default="RELEASE_NOTE.md")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    return parser


def run(command: list[str]) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, check=True)


def validate_release_zip(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing release ZIP: {path}")
    with ZipFile(path) as archive:
        entries = archive.namelist()
    expected = expected_release_entries()
    if entries != expected:
        missing = sorted(set(expected) - set(entries))
        extra = sorted(set(entries) - set(expected))
        raise SystemExit(
            f"{path} does not match the release layout. "
            f"Missing: {missing or 'none'}; extra: {extra or 'none'}"
        )


def write_sha256(path: Path, output: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    output.write_text(f"{digest}  {path.name}\n")
    print(f"Wrote {output}")


def copy_release_note(source: Path, output: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Missing release note: {source}")
    shutil.copyfile(source, output)
    print(f"Wrote {output}")


def main() -> None:
    args = build_parser().parse_args()
    version = normalize_version(args.version)
    dist_dir = Path(args.dist_dir)
    zip_path = dist_dir / release_zip_name(version)

    if not args.skip_tests:
        run([args.make, "test", f"PYTHON={args.python}"])
    if not args.skip_build:
        run([args.make, "dist", f"VERSION={version}", f"PYTHON={args.python}"])

    validate_release_zip(zip_path)
    write_sha256(zip_path, dist_dir / checksum_name(version))
    copy_release_note(Path(args.release_note), dist_dir / release_note_name(version))
    print(f"Release package ready: {zip_path}")


if __name__ == "__main__":
    main()
