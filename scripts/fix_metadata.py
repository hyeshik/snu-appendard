#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from fontTools.ttLib import TTFont


FAMILY_NAME = "SNU Appendard"
POSTSCRIPT_FAMILY_NAME = "SNUAppendard"
VERSION = "0.6.0"
VENDOR_ID = "HCHK"
DEFAULT_ITALIC_ANGLE = -10.0
TARGET_UPM = 1000

WEIGHT_CLASSES = {
    "Thin": 100,
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
    "Black": 900,
}

NAME_IDS_TO_REWRITE = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 16, 17, 18})


class FontMetadata(NamedTuple):
    style: str
    italic: bool
    weight_class: int
    names: dict[int, str]


class VerticalMetrics(NamedTuple):
    hhea_ascent: int
    hhea_descent: int
    hhea_line_gap: int
    hhea_caret_offset: int
    typo_ascender: int
    typo_descender: int
    typo_line_gap: int
    win_ascent: int
    win_descent: int
    subscript_x_size: int
    subscript_y_size: int
    subscript_x_offset: int
    subscript_y_offset: int
    superscript_x_size: int
    superscript_y_size: int
    superscript_x_offset: int
    superscript_y_offset: int
    strikeout_size: int
    strikeout_position: int
    x_height: int
    cap_height: int
    post_underline_position: int
    post_underline_thickness: int
    cff_underline_position: int | None
    cff_underline_thickness: int | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize generated SNU Appendard OTF metadata with fontTools."
    )
    parser.add_argument("--input-dir", default="dist/otf")
    parser.add_argument("--font", action="append", default=[])
    parser.add_argument("--pretendard-dir", default="sources/pretendard")
    parser.add_argument("--versions-lock", default="versions.lock")
    return parser


def read_versions_lock(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def find_font_file(root: Path, stem: str, extensions: tuple[str, ...] = (".ttf", ".otf")) -> Path:
    candidates: list[Path] = []
    for extension in extensions:
        candidates.extend(root.rglob(f"{stem}{extension}"))
    candidates = [
        path
        for path in candidates
        if "__MACOSX" not in path.parts and not path.name.startswith("._")
    ]
    if not candidates:
        raise FileNotFoundError(f"Could not find {stem} under {root}")
    return sorted(candidates, key=lambda path: (len(path.parts), str(path)))[0]


def parse_output_filename(filename: str | Path) -> tuple[str, bool]:
    path = Path(filename)
    if path.suffix != ".otf":
        raise ValueError(f"Expected an .otf filename: {path.name}")
    prefix = f"{POSTSCRIPT_FAMILY_NAME}-"
    if not path.stem.startswith(prefix):
        raise ValueError(f"Expected filename prefix {prefix}: {path.name}")

    style_token = path.stem.removeprefix(prefix)
    italic = style_token.endswith("Italic")
    style = style_token[: -len("Italic")] if italic else style_token
    if style not in WEIGHT_CLASSES:
        raise ValueError(f"Unknown SNU Appendard style in {path.name}: {style}")
    return style, italic


def style_name(style: str, italic: bool) -> str:
    if not italic:
        return style
    if style == "Regular":
        return "Italic"
    return f"{style} Italic"


def postscript_style_name(style: str, italic: bool) -> str:
    if italic and style == "Regular":
        return "RegularItalic"
    return style_name(style, italic).replace(" ", "")


def fs_selection(weight_class: int, italic: bool) -> int:
    value = 0
    if italic:
        value |= 0x01
    if weight_class >= 700:
        value |= 0x20
    if not italic and weight_class == 400:
        value |= 0x40
    return value


def mac_style(weight_class: int, italic: bool) -> int:
    value = 0
    if weight_class >= 700:
        value |= 0x01
    if italic:
        value |= 0x02
    return value


def scale_metric(value: int, source_upm: int, target_upm: int) -> int:
    return round(value * target_upm / source_upm)


def scale_design_metrics(
    values: dict[str, int | None],
    source_upm: int,
    target_upm: int,
) -> dict[str, int | None]:
    return {
        key: None if value is None else scale_metric(value, source_upm, target_upm)
        for key, value in values.items()
    }


def maybe_getattr(obj, name: str):
    try:
        return getattr(obj, name)
    except AttributeError:
        return None


def read_vertical_metrics(path: Path, target_upm: int) -> VerticalMetrics:
    with TTFont(str(path)) as font:
        source_upm = font["head"].unitsPerEm
        hhea_table = font["hhea"]
        os2_table = font["OS/2"]
        post_table = font["post"]
        cff_top = font["CFF "].cff.topDictIndex[0] if "CFF " in font else None
        metrics = scale_design_metrics(
            {
                "hhea_ascent": hhea_table.ascent,
                "hhea_descent": hhea_table.descent,
                "hhea_line_gap": hhea_table.lineGap,
                "hhea_caret_offset": hhea_table.caretOffset,
                "typo_ascender": os2_table.sTypoAscender,
                "typo_descender": os2_table.sTypoDescender,
                "typo_line_gap": os2_table.sTypoLineGap,
                "win_ascent": os2_table.usWinAscent,
                "win_descent": os2_table.usWinDescent,
                "subscript_x_size": os2_table.ySubscriptXSize,
                "subscript_y_size": os2_table.ySubscriptYSize,
                "subscript_x_offset": os2_table.ySubscriptXOffset,
                "subscript_y_offset": os2_table.ySubscriptYOffset,
                "superscript_x_size": os2_table.ySuperscriptXSize,
                "superscript_y_size": os2_table.ySuperscriptYSize,
                "superscript_x_offset": os2_table.ySuperscriptXOffset,
                "superscript_y_offset": os2_table.ySuperscriptYOffset,
                "strikeout_size": os2_table.yStrikeoutSize,
                "strikeout_position": os2_table.yStrikeoutPosition,
                "x_height": os2_table.sxHeight,
                "cap_height": os2_table.sCapHeight,
                "post_underline_position": post_table.underlinePosition,
                "post_underline_thickness": post_table.underlineThickness,
                "cff_underline_position": maybe_getattr(cff_top, "UnderlinePosition"),
                "cff_underline_thickness": maybe_getattr(cff_top, "UnderlineThickness"),
            },
            source_upm,
            target_upm,
        )
        return VerticalMetrics(**metrics)


def metadata_for_filename(
    filename: str | Path,
    versions: dict[str, str],
    build_stamp: str | None = None,
) -> FontMetadata:
    style, italic = parse_output_filename(filename)
    output_style = style_name(style, italic)
    ps_name = f"{POSTSCRIPT_FAMILY_NAME}-{postscript_style_name(style, italic)}"
    full_name = f"{FAMILY_NAME} {output_style}"
    stamp = build_stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    copyright_text = (
        "Copyright (c) Hyung-jin Kil and Pretendard contributors; "
        "Copyright (c) Rasmus Andersson and Inter contributors; "
        "modified by Hyeshik Chang as SNU Appendard."
    )
    notice = (
        "SNU Appendard is a derivative of Pretendard and Inter. "
        "It uses the upstream names only for attribution."
    )

    return FontMetadata(
        style=style,
        italic=italic,
        weight_class=WEIGHT_CLASSES[style],
        names={
            0: copyright_text,
            1: FAMILY_NAME,
            2: output_style,
            3: f"{VERSION};{VENDOR_ID};{ps_name};{stamp}",
            4: full_name,
            5: f"Version {VERSION}",
            6: ps_name,
            7: notice,
            8: "Hyeshik Chang",
            9: "Hyeshik Chang",
            13: "SIL Open Font License, Version 1.1",
            14: "https://openfontlicense.org",
            16: FAMILY_NAME,
            17: output_style,
            18: full_name,
        },
    )


def replace_name_records(font: TTFont, metadata: FontMetadata) -> None:
    name_table = font["name"]
    name_table.names = [
        record for record in name_table.names if record.nameID not in NAME_IDS_TO_REWRITE
    ]
    for name_id, value in sorted(metadata.names.items()):
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 1, 0, 0)


def font_revision(version: str = VERSION) -> float:
    """``head.fontRevision`` for our dotted version string.

    FontForge leaves Pretendard's own revision in the generated ``head`` table,
    so a build would otherwise report itself as Pretendard's 1.309 no matter what
    the name records say. Minor and patch become decimal places, matching what
    FontForge writes for the sibling families: ``0.2.0`` is ``0.2`` and ``0.2.1``
    is ``0.201``. That mapping only stays unambiguous while minor stays below 10
    and patch below 100, so it refuses anything larger rather than silently
    shipping a revision that collides with another release.
    """
    parts = version.split(".")
    if len(parts) not in (2, 3):
        raise ValueError(f"Expected a major.minor[.patch] version: {version}")
    major, minor = int(parts[0]), int(parts[1])
    patch = int(parts[2]) if len(parts) == 3 else 0
    if not 0 <= minor < 10 or not 0 <= patch < 100:
        raise ValueError(
            f"Version {version} cannot be mapped to a unique head.fontRevision; "
            "pick a wider encoding before releasing it."
        )
    return round(major + minor / 10 + patch / 1000, 6)


def caret_slope_run(italic_angle: float, rise: int = TARGET_UPM) -> int:
    if italic_angle == 0:
        return 0
    return round(math.tan(math.radians(abs(italic_angle))) * rise)


def normalize_style_tables(font: TTFont, metadata: FontMetadata) -> None:
    if "OS/2" in font:
        os2_table = font["OS/2"]
        os2_table.usWeightClass = metadata.weight_class
        os2_table.usWidthClass = 5
        os2_table.achVendID = VENDOR_ID
        os2_table.fsSelection = (
            os2_table.fsSelection & ~(0x01 | 0x20 | 0x40)
        ) | fs_selection(metadata.weight_class, metadata.italic)

    if "head" in font:
        head_table = font["head"]
        head_table.fontRevision = font_revision()
        head_table.macStyle = (
            head_table.macStyle & ~(0x01 | 0x02)
        ) | mac_style(metadata.weight_class, metadata.italic)

    italic_angle = 0.0
    if "post" in font:
        post_table = font["post"]
        if metadata.italic:
            italic_angle = post_table.italicAngle or DEFAULT_ITALIC_ANGLE
            post_table.italicAngle = italic_angle
        else:
            post_table.italicAngle = 0

    if "hhea" in font:
        hhea_table = font["hhea"]
        hhea_table.caretSlopeRise = TARGET_UPM
        hhea_table.caretSlopeRun = caret_slope_run(italic_angle)


def normalize_cff_version(font: TTFont) -> None:
    if "CFF " not in font:
        return
    top_dict = font["CFF "].cff.topDictIndex[0]
    top_dict.version = VERSION
    if hasattr(top_dict, "CIDFontVersion"):
        top_dict.CIDFontVersion = font_revision()


def normalize_vertical_metrics(font: TTFont, metrics: VerticalMetrics) -> None:
    if "hhea" in font:
        hhea_table = font["hhea"]
        hhea_table.ascent = metrics.hhea_ascent
        hhea_table.descent = metrics.hhea_descent
        hhea_table.lineGap = metrics.hhea_line_gap
        hhea_table.caretOffset = metrics.hhea_caret_offset

    if "OS/2" in font:
        os2_table = font["OS/2"]
        os2_table.sTypoAscender = metrics.typo_ascender
        os2_table.sTypoDescender = metrics.typo_descender
        os2_table.sTypoLineGap = metrics.typo_line_gap
        os2_table.usWinAscent = metrics.win_ascent
        os2_table.usWinDescent = metrics.win_descent
        os2_table.ySubscriptXSize = metrics.subscript_x_size
        os2_table.ySubscriptYSize = metrics.subscript_y_size
        os2_table.ySubscriptXOffset = metrics.subscript_x_offset
        os2_table.ySubscriptYOffset = metrics.subscript_y_offset
        os2_table.ySuperscriptXSize = metrics.superscript_x_size
        os2_table.ySuperscriptYSize = metrics.superscript_y_size
        os2_table.ySuperscriptXOffset = metrics.superscript_x_offset
        os2_table.ySuperscriptYOffset = metrics.superscript_y_offset
        os2_table.yStrikeoutSize = metrics.strikeout_size
        os2_table.yStrikeoutPosition = metrics.strikeout_position
        os2_table.sxHeight = metrics.x_height
        os2_table.sCapHeight = metrics.cap_height

    if "post" in font:
        post_table = font["post"]
        post_table.underlinePosition = metrics.post_underline_position
        post_table.underlineThickness = metrics.post_underline_thickness

    if "CFF " in font:
        cff_top = font["CFF "].cff.topDictIndex[0]
        if metrics.cff_underline_position is not None:
            cff_top.UnderlinePosition = metrics.cff_underline_position
        if metrics.cff_underline_thickness is not None:
            cff_top.UnderlineThickness = metrics.cff_underline_thickness


def apply_metadata(path: Path, versions: dict[str, str], pretendard_dir: Path | None) -> FontMetadata:
    metadata = metadata_for_filename(path.name, versions)
    font = TTFont(str(path))
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        replace_name_records(font, metadata)
        normalize_style_tables(font, metadata)
        normalize_cff_version(font)
        if pretendard_dir is not None:
            source_path = find_font_file(pretendard_dir, f"Pretendard-{metadata.style}")
            normalize_vertical_metrics(
                font,
                read_vertical_metrics(source_path, font["head"].unitsPerEm),
            )
        font.save(str(tmp_path))
    finally:
        font.close()
    tmp_path.replace(path)
    return metadata


def input_paths(args) -> list[Path]:
    if args.font:
        return [Path(font_path) for font_path in args.font]
    return sorted(Path(args.input_dir).glob(f"{POSTSCRIPT_FAMILY_NAME}-*.otf"))


def main() -> None:
    args = build_parser().parse_args()
    versions = read_versions_lock(Path(args.versions_lock))
    pretendard_dir = Path(args.pretendard_dir) if args.pretendard_dir else None
    paths = input_paths(args)
    if not paths:
        raise SystemExit("No SNU Appendard OTFs found to normalize.")

    for path in paths:
        metadata = apply_metadata(path, versions, pretendard_dir)
        print(
            f"{path}: metadata={metadata.names[6]}, "
            f"style={metadata.names[2]}, weight={metadata.weight_class}"
        )


if __name__ == "__main__":
    main()
