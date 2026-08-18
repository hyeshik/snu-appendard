#!/usr/bin/env fontforge -lang=py -script
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, NamedTuple


FAMILY_NAME = "SNU Appendard"
POSTSCRIPT_FAMILY_NAME = "SNUAppendard"
FILE_FAMILY_NAME = POSTSCRIPT_FAMILY_NAME
VERSION = "0.2.0"
VENDOR_ID = "HCHK"
DEFAULT_OUTPUT_DIR = "dist/otf"
TARGET_UPM = 1000


class WeightSpec(NamedTuple):
    style: str
    weight_class: int
    pretendard_stem: str
    inter_upright_stem: str
    inter_italic_stem: str


class AffineTransform(NamedTuple):
    scale_x: float = 1.0
    scale_y: float = 1.0
    translate_y: float = 0.0


WEIGHT_SPECS = (
    WeightSpec("Thin", 100, "Pretendard-Thin", "Inter-Thin", "Inter-ThinItalic"),
    WeightSpec(
        "ExtraLight",
        200,
        "Pretendard-ExtraLight",
        "Inter-ExtraLight",
        "Inter-ExtraLightItalic",
    ),
    WeightSpec("Light", 300, "Pretendard-Light", "Inter-Light", "Inter-LightItalic"),
    WeightSpec("Regular", 400, "Pretendard-Regular", "Inter-Regular", "Inter-Italic"),
    WeightSpec("Medium", 500, "Pretendard-Medium", "Inter-Medium", "Inter-MediumItalic"),
    WeightSpec(
        "SemiBold",
        600,
        "Pretendard-SemiBold",
        "Inter-SemiBold",
        "Inter-SemiBoldItalic",
    ),
    WeightSpec("Bold", 700, "Pretendard-Bold", "Inter-Bold", "Inter-BoldItalic"),
    WeightSpec(
        "ExtraBold",
        800,
        "Pretendard-ExtraBold",
        "Inter-ExtraBold",
        "Inter-ExtraBoldItalic",
    ),
    WeightSpec("Black", 900, "Pretendard-Black", "Inter-Black", "Inter-BlackItalic"),
)


CJK_CODEPOINT_RANGES = (
    (0x1100, 0x11FF),
    (0x2E80, 0x2EFF),
    (0x2F00, 0x2FDF),
    (0x3000, 0x303F),
    (0x3040, 0x309F),
    (0x30A0, 0x30FF),
    (0x3100, 0x312F),
    (0x3130, 0x318F),
    (0x31A0, 0x31BF),
    (0x31C0, 0x31EF),
    (0x31F0, 0x31FF),
    (0x3200, 0x32FF),
    (0x3300, 0x33FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xA960, 0xA97F),
    (0xAC00, 0xD7AF),
    (0xD7B0, 0xD7FF),
    (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
    (0x30000, 0x3134F),
)

CJK_CONTEXT_SYMBOL_RANGES = (
    (0x20D0, 0x20FF),  # enclosing combining marks
    (0x2460, 0x24FF),  # enclosed alphanumerics
    (0x2700, 0x27BF),  # dingbats, including circled digits
    (0x1F100, 0x1F1FF),  # enclosed alphanumeric supplement
)

PRIVATE_USE_RANGES = (
    (0xE000, 0xF8FF),
    (0xF0000, 0xFFFFD),
    (0x100000, 0x10FFFD),
)


@contextlib.contextmanager
def suppress_c_stderr(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return

    saved_stderr = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_stderr, 2)
        os.close(saved_stderr)
        os.close(devnull)


def style_name(style: str, italic: bool) -> str:
    if not italic:
        return style
    if style == "Regular":
        return "Italic"
    return f"{style} Italic"


def typographic_style_name(style: str, italic: bool) -> str:
    if italic and style == "Regular":
        return "Regular Italic"
    return style_name(style, italic)


def postscript_style_name(style: str, italic: bool) -> str:
    return style_name(style, italic).replace(" ", "")


def output_filename(style: str, italic: bool) -> str:
    return f"{FILE_FAMILY_NAME}-{postscript_style_name(style, italic)}.otf"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build SNU Appendard OTFs from Pretendard and Inter sources."
    )
    parser.add_argument("--all", action="store_true", help="Build all weights.")
    parser.add_argument("--weight", choices=[spec.style for spec in WEIGHT_SPECS])
    parser.add_argument("--pretendard")
    parser.add_argument("--inter")
    parser.add_argument("--inter-italic")
    parser.add_argument("--pretendard-dir", default="sources/pretendard")
    parser.add_argument("--inter-dir", default="sources/inter")
    parser.add_argument("--output")
    parser.add_argument("--output-italic")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--transform", default="build/mapping_report.json")
    parser.add_argument("--versions-lock", default="versions.lock")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--verbose-fontforge", action="store_true")
    return parser


def spec_by_style(style: str) -> WeightSpec:
    specs = {spec.style: spec for spec in WEIGHT_SPECS}
    try:
        return specs[style]
    except KeyError as exc:
        raise SystemExit(f"Unknown weight: {style}") from exc


def is_cjk_codepoint(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in CJK_CODEPOINT_RANGES)


def is_cjk_context_symbol(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in CJK_CONTEXT_SYMBOL_RANGES)


def is_private_use_codepoint(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in PRIVATE_USE_RANGES)


def should_keep_pretendard_codepoint(codepoint: int) -> bool:
    return (
        is_cjk_codepoint(codepoint)
        or is_cjk_context_symbol(codepoint)
        or is_private_use_codepoint(codepoint)
    )


def should_replace_codepoint(codepoint: int) -> bool:
    return codepoint >= 0 and not should_keep_pretendard_codepoint(codepoint)


def should_import_inter_glyphs(italic: bool) -> bool:
    return True


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


def resolve_font_source(explicit_path: str | None, root: Path, stem: str) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    return find_font_file(root, stem)


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


def load_transform(path: Path, weight: str) -> AffineTransform:
    if not path.is_file():
        return AffineTransform()
    report = json.loads(path.read_text())
    weight_report = report.get("weights", {}).get(weight, {})
    return AffineTransform(
        scale_x=float(weight_report.get("scale_x", 1.0)),
        scale_y=float(weight_report.get("scale_y", 1.0)),
        translate_y=float(weight_report.get("translate_y", 0.0)),
    )


def unicode_map(font) -> dict[int, object]:
    return {glyph.unicode: glyph for glyph in font.glyphs() if glyph.unicode >= 0}


def open_font(fontforge, path: Path, quiet: bool):
    with suppress_c_stderr(quiet):
        return fontforge.open(str(path))


def copy_glyph(source_font, source_glyph, target_font, target_glyph) -> None:
    source_font.selection.none()
    source_font.selection.select(source_glyph.glyphname)
    source_font.copy()
    target_font.selection.none()
    target_font.selection.select(target_glyph.glyphname)
    target_font.paste()


def source_to_target_upm_scale(source_upm: int, target_upm: int) -> float:
    return target_upm / source_upm


def glyph_transform_matrix(
    transform: AffineTransform,
    source_upm: int,
    target_upm: int,
) -> tuple[float, int, int, float, int, float]:
    unit_scale = source_to_target_upm_scale(source_upm, target_upm)
    return (
        transform.scale_x * unit_scale,
        0,
        0,
        transform.scale_y * unit_scale,
        0,
        transform.translate_y * target_upm,
    )


def transformed_width(
    width: float,
    transform: AffineTransform,
    source_upm: int,
    target_upm: int,
    preserve_spacing: bool = False,
    original_width: int | None = None,
) -> int:
    if preserve_spacing:
        if original_width is None:
            raise ValueError("original_width is required when preserve_spacing is true")
        return original_width
    return round(width * transform.scale_x * source_to_target_upm_scale(source_upm, target_upm))


def integer_fontforge_metric(value: float) -> int:
    return int(round(value))


def import_non_cjk_glyphs(
    base_font,
    inter_font,
    transform: AffineTransform,
    preserve_spacing: bool,
) -> int:
    base_by_codepoint = unicode_map(base_font)
    inter_by_codepoint = unicode_map(inter_font)
    changed = 0
    glyph_matrix = glyph_transform_matrix(transform, inter_font.em, base_font.em)

    for codepoint in sorted(base_by_codepoint):
        if not should_replace_codepoint(codepoint):
            continue
        source_glyph = inter_by_codepoint.get(codepoint)
        if source_glyph is None:
            continue
        target_glyph = base_by_codepoint[codepoint]
        original_width = target_glyph.width
        original_lsb = getattr(target_glyph, "left_side_bearing", None)
        copy_glyph(inter_font, source_glyph, base_font, target_glyph)
        target_glyph.transform(glyph_matrix)
        target_glyph.width = transformed_width(
            source_glyph.width,
            transform,
            source_upm=inter_font.em,
            target_upm=base_font.em,
            preserve_spacing=preserve_spacing,
            original_width=original_width,
        )
        if preserve_spacing and original_lsb is not None:
            target_glyph.left_side_bearing = integer_fontforge_metric(original_lsb)
            target_glyph.width = original_width
        changed += 1
    return changed


def os2_stylemap(weight_class: int, italic: bool) -> int:
    stylemap = 0
    if italic:
        stylemap |= 1
    if weight_class >= 700:
        stylemap |= 32
    if not italic and weight_class == 400:
        stylemap |= 64
    return stylemap


def set_if_present(obj, name: str, value) -> bool:
    if hasattr(obj, name):
        setattr(obj, name, value)
        return True
    return False


def caret_slope_for_angle(italic_angle: float, rise: int = TARGET_UPM) -> tuple[int, int]:
    if italic_angle == 0:
        return rise, 0
    run = round(math.tan(math.radians(abs(italic_angle))) * rise)
    return rise, run


def rewrite_metadata(
    font,
    spec: WeightSpec,
    italic: bool,
    italic_angle: float,
    versions: dict[str, str],
) -> None:
    output_style = style_name(spec.style, italic)
    preferred_style = typographic_style_name(spec.style, italic)
    ps_name = f"{POSTSCRIPT_FAMILY_NAME}-{postscript_style_name(spec.style, italic)}"
    full_name = f"{FAMILY_NAME} {output_style}"
    build_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    upstream = "Pretendard {pret}; Inter {inter}".format(
        pret=versions.get("PRETENDARD_TAG", "unknown"),
        inter=versions.get("INTER_TAG", "unknown"),
    )
    copyright_text = (
        "Copyright (c) Hyung-jin Kil and Pretendard contributors; "
        "Copyright (c) Rasmus Andersson and Inter contributors; "
        "modified by Hyeshik Chang as SNU Appendard."
    )

    font.familyname = FAMILY_NAME
    font.fullname = full_name
    font.fontname = ps_name
    font.weight = "Normal" if spec.style == "Regular" else spec.style
    font.version = VERSION
    font.copyright = copyright_text
    font.os2_weight = spec.weight_class
    font.os2_width = 5
    font.os2_vendor = VENDOR_ID
    font.os2_stylemap = os2_stylemap(spec.weight_class, italic)
    font.italicangle = italic_angle if italic else 0

    set_if_present(font, "macstyle", (2 if italic else 0) | (1 if spec.weight_class >= 700 else 0))
    rise, run = caret_slope_for_angle(italic_angle if italic else 0)
    set_if_present(font, "hhea_caretSlopeRise", rise)
    set_if_present(font, "hhea_caretSlopeRun", run)

    notice = (
        "SNU Appendard is a derivative of Pretendard and Inter. "
        "It uses the upstream names only for attribution."
    )
    font.sfnt_names = (
        ("English (US)", "Copyright", copyright_text),
        ("English (US)", "Family", FAMILY_NAME),
        ("English (US)", "SubFamily", output_style),
        ("English (US)", "UniqueID", f"{VERSION};{VENDOR_ID};{ps_name};{build_stamp}"),
        ("English (US)", "Fullname", full_name),
        ("English (US)", "Version", f"Version {VERSION}; {upstream}; build {build_stamp}"),
        ("English (US)", "PostScriptName", ps_name),
        ("English (US)", "Trademark", notice),
        ("English (US)", "Manufacturer", "Hyeshik Chang"),
        ("English (US)", "Designer", "Hyeshik Chang"),
        ("English (US)", "Preferred Family", FAMILY_NAME),
        ("English (US)", "Preferred Styles", preferred_style),
        ("English (US)", "Compatible Full", full_name),
        ("English (US)", "License", "SIL Open Font License, Version 1.1"),
        ("English (US)", "License URL", "https://openfontlicense.org"),
    )


def verify_otf(path: Path) -> None:
    try:
        from fontTools.ttLib import TTFont
    except ModuleNotFoundError:
        print(f"Skipping table verification for {path}: fontTools is not installed.")
        return

    with TTFont(str(path)) as font:
        errors = []
        if font["head"].unitsPerEm != TARGET_UPM:
            errors.append(f"head.unitsPerEm is {font['head'].unitsPerEm}, expected {TARGET_UPM}")
        if "CFF " not in font:
            errors.append("CFF table is missing")
        if "glyf" in font:
            errors.append("glyf table should not be present in OTF output")
        if errors:
            raise SystemExit(f"{path} failed verification: " + "; ".join(errors))


def generate_variant(
    fontforge,
    pretendard_path: Path,
    inter_path: Path | None,
    output_path: Path,
    spec: WeightSpec,
    italic: bool,
    transform: AffineTransform,
    versions: dict[str, str],
    quiet: bool,
    skip_verify: bool,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_font = open_font(fontforge, pretendard_path, quiet)
    inter_font = open_font(fontforge, inter_path, quiet) if inter_path is not None else None
    try:
        imported = 0
        italic_angle = 0
        if should_import_inter_glyphs(italic):
            if inter_font is None:
                raise SystemExit("Inter glyph import requires an Inter source font")
            with suppress_c_stderr(quiet):
                imported = import_non_cjk_glyphs(
                    base_font,
                    inter_font,
                    transform,
                    preserve_spacing=not italic,
                )
            if italic:
                italic_angle = getattr(inter_font, "italicangle", 0)
        rewrite_metadata(base_font, spec, italic, italic_angle, versions)
        base_font.em = TARGET_UPM
        with suppress_c_stderr(quiet):
            base_font.autoHint()
        with suppress_c_stderr(quiet):
            validation_state = base_font.validate()
        with suppress_c_stderr(quiet):
            base_font.generate(str(output_path), flags=("opentype",))
        if not skip_verify:
            verify_otf(output_path)
        print(
            f"{output_path}: imported={imported}, italic={italic}, "
            f"transform=({transform.scale_x:.6f},{transform.scale_y:.6f},"
            f"{transform.translate_y:.6f}), validate=0x{validation_state:x}"
        )
        return output_path
    finally:
        if inter_font is not None:
            inter_font.close()
        base_font.close()


def build_explicit(fontforge, args, versions: dict[str, str], quiet: bool) -> list[Path]:
    if not args.weight:
        raise SystemExit("--weight is required unless --all is used")
    for required in ("output", "output_italic"):
        if getattr(args, required) is None:
            raise SystemExit(f"--{required.replace('_', '-')} is required")

    spec = spec_by_style(args.weight)
    transform = load_transform(Path(args.transform), spec.style)
    pretendard_path = resolve_font_source(
        args.pretendard,
        Path(args.pretendard_dir),
        spec.pretendard_stem,
    )
    upright_path = resolve_font_source(
        args.inter,
        Path(args.inter_dir),
        spec.inter_upright_stem,
    )
    italic_path = resolve_font_source(
        args.inter_italic,
        Path(args.inter_dir),
        spec.inter_italic_stem,
    )
    built = [
        generate_variant(
            fontforge,
            pretendard_path,
            upright_path,
            Path(args.output),
            spec,
            False,
            transform,
            versions,
            quiet,
            args.skip_verify,
        ),
        generate_variant(
            fontforge,
            pretendard_path,
            italic_path,
            Path(args.output_italic),
            spec,
            True,
            transform,
            versions,
            quiet,
            args.skip_verify,
        ),
    ]
    return built


def build_all(fontforge, args, versions: dict[str, str], quiet: bool) -> list[Path]:
    pretendard_dir = Path(args.pretendard_dir)
    inter_dir = Path(args.inter_dir)
    output_dir = Path(args.output_dir)
    built = []

    for spec in WEIGHT_SPECS:
        pretendard_path = find_font_file(pretendard_dir, spec.pretendard_stem)
        upright_path = find_font_file(inter_dir, spec.inter_upright_stem)
        italic_path = find_font_file(inter_dir, spec.inter_italic_stem)
        transform = load_transform(Path(args.transform), spec.style)
        built.append(
            generate_variant(
                fontforge,
                pretendard_path,
                upright_path,
                output_dir / output_filename(spec.style, False),
                spec,
                False,
                transform,
                versions,
                quiet,
                args.skip_verify,
            )
        )
        built.append(
            generate_variant(
                fontforge,
                pretendard_path,
                italic_path,
                output_dir / output_filename(spec.style, True),
                spec,
                True,
                transform,
                versions,
                quiet,
                args.skip_verify,
            )
        )
    return built


def main() -> None:
    args = build_parser().parse_args()
    try:
        import fontforge
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Run this script with FontForge: "
            "fontforge -lang=py -script scripts/build_appendard.py"
        ) from exc

    versions = read_versions_lock(Path(args.versions_lock))
    quiet = not args.verbose_fontforge
    built = build_all(fontforge, args, versions, quiet) if args.all else build_explicit(fontforge, args, versions, quiet)
    print(f"Built {len(built)} font(s).")


if __name__ == "__main__":
    main()
