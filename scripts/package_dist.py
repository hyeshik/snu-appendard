#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


FAMILY_PREFIX = "SNUAppendard"
STYLE_NAMES = (
    "Thin",
    "ThinItalic",
    "ExtraLight",
    "ExtraLightItalic",
    "Light",
    "LightItalic",
    "Regular",
    "Italic",
    "Medium",
    "MediumItalic",
    "SemiBold",
    "SemiBoldItalic",
    "Bold",
    "BoldItalic",
    "ExtraBold",
    "ExtraBoldItalic",
    "Black",
    "BlackItalic",
)
EXPECTED_OTF_FILENAMES = [f"{FAMILY_PREFIX}-{style}.otf" for style in STYLE_NAMES]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package SNU Appendard release files.")
    parser.add_argument("--input-dir", default="dist/otf")
    parser.add_argument("--output", default="dist/SNUAppendard-v0.1.0.zip")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional file to include at the ZIP root.",
    )
    return parser


def find_expected_otfs(input_dir: Path) -> list[Path]:
    paths = [input_dir / filename for filename in EXPECTED_OTF_FILENAMES]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing expected OTF file(s): " + ", ".join(missing)
        )
    return paths


def write_zip(output: Path, fonts: list[Path], include_paths: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for font_path in fonts:
            archive.write(font_path, arcname=f"otf/{font_path.name}")
            print(f"Added otf/{font_path.name}")
        for include_path in include_paths:
            if not include_path.is_file():
                raise FileNotFoundError(f"Missing include file: {include_path}")
            archive.write(include_path, arcname=include_path.name)
            print(f"Added {include_path.name}")
    print(f"Wrote {output}")


def main() -> None:
    args = build_parser().parse_args()
    fonts = find_expected_otfs(Path(args.input_dir))
    includes = [Path(path) for path in args.include]
    write_zip(Path(args.output), fonts, includes)


if __name__ == "__main__":
    main()
