#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple


REFERENCE_GLYPHS = ("H", "n", "o", "x", "I", "A", "g", "period")
DEFAULT_TOLERANCE_UNITS = 4


class GlyphMeasurements(NamedTuple):
    bounds: tuple[float, float, float, float] | None
    advance: float
    lsb: float


class FontMeasurements(NamedTuple):
    upm: int
    cap_height: float
    x_height: float
    glyphs: dict[str, GlyphMeasurements]


class AffineTransform(NamedTuple):
    scale_x: float
    scale_y: float
    translate_y: float


class WeightSpec(NamedTuple):
    style: str
    pretendard_stem: str
    inter_stem: str


WEIGHT_SPECS = (
    WeightSpec("Thin", "Pretendard-Thin", "Inter-Thin"),
    WeightSpec("ExtraLight", "Pretendard-ExtraLight", "Inter-ExtraLight"),
    WeightSpec("Light", "Pretendard-Light", "Inter-Light"),
    WeightSpec("Regular", "Pretendard-Regular", "Inter-Regular"),
    WeightSpec("Medium", "Pretendard-Medium", "Inter-Medium"),
    WeightSpec("SemiBold", "Pretendard-SemiBold", "Inter-SemiBold"),
    WeightSpec("Bold", "Pretendard-Bold", "Inter-Bold"),
    WeightSpec("ExtraBold", "Pretendard-ExtraBold", "Inter-ExtraBold"),
    WeightSpec("Black", "Pretendard-Black", "Inter-Black"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Derive Inter-to-Pretendard non-CJK glyph transforms."
    )
    parser.add_argument("--pretendard-dir", default="sources/pretendard")
    parser.add_argument("--inter-dir", default="sources/inter")
    parser.add_argument("--output", default="build/mapping_report.json")
    parser.add_argument(
        "--tolerance-units",
        type=int,
        default=DEFAULT_TOLERANCE_UNITS,
        help="Residual threshold in 2048-UPM reference units.",
    )
    parser.add_argument(
        "--allow-large-residuals",
        action="store_true",
        help="Write the report without failing when residuals exceed tolerance.",
    )
    return parser


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


def _load_fonttools():
    try:
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.ttLib import TTFont
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "fontTools is required for mapping analysis. Install it with "
            "`python3 -m pip install fonttools` or your system package manager."
        ) from exc
    return TTFont, BoundsPen


def _best_cmap(font) -> dict[int, str]:
    cmap = font.getBestCmap()
    if not cmap:
        raise ValueError("Font has no Unicode cmap")
    return cmap


def _glyph_bounds(font, glyph_name: str):
    _, BoundsPen = _load_fonttools()
    glyph_set = font.getGlyphSet()
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


def _metric_or_zero(os2, name: str) -> int:
    return int(getattr(os2, name, 0) or 0)


def read_measurements(path: Path, reference_glyphs: tuple[str, ...] = REFERENCE_GLYPHS) -> FontMeasurements:
    TTFont, _ = _load_fonttools()
    with TTFont(str(path)) as font:
        upm = int(font["head"].unitsPerEm)
        os2 = font["OS/2"]
        cmap = _best_cmap(font)
        hmtx = font["hmtx"].metrics
        cap_height = _metric_or_zero(os2, "sCapHeight")
        x_height = _metric_or_zero(os2, "sxHeight")
        if not cap_height:
            cap_name = cmap.get(ord("H"))
            cap_bounds = _glyph_bounds(font, cap_name) if cap_name else None
            cap_height = int(cap_bounds[3]) if cap_bounds else upm
        if not x_height:
            x_name = cmap.get(ord("x"))
            x_bounds = _glyph_bounds(font, x_name) if x_name else None
            x_height = int(x_bounds[3]) if x_bounds else 0

        glyphs: dict[str, GlyphMeasurements] = {}
        for label in reference_glyphs:
            codepoint = ord(".") if label == "period" else ord(label)
            glyph_name = cmap.get(codepoint)
            if not glyph_name:
                continue
            advance, lsb = hmtx[glyph_name]
            bounds = _glyph_bounds(font, glyph_name)
            normalized_bounds = (
                None
                if bounds is None
                else tuple(value / upm for value in bounds)
            )
            glyphs[label] = GlyphMeasurements(
                bounds=normalized_bounds,
                advance=advance / upm,
                lsb=lsb / upm,
            )

        return FontMeasurements(
            upm=upm,
            cap_height=cap_height / upm,
            x_height=x_height / upm,
            glyphs=glyphs,
        )


def compute_transform(pretendard: FontMeasurements, inter: FontMeasurements) -> AffineTransform:
    if "H" not in pretendard.glyphs or "H" not in inter.glyphs:
        raise ValueError("Both fonts must contain H for transform derivation")
    if not pretendard.cap_height or not inter.cap_height:
        raise ValueError("Both fonts must expose a non-zero cap height")

    pretendard_h = pretendard.glyphs["H"]
    inter_h = inter.glyphs["H"]
    if not pretendard_h.bounds or not inter_h.bounds:
        raise ValueError("Both fonts must expose H bounds")
    if not inter_h.advance:
        raise ValueError("Inter H has zero advance width")

    scale_y = pretendard.cap_height / inter.cap_height
    translate_y = pretendard_h.bounds[1] - inter_h.bounds[1] * scale_y
    scale_x = pretendard_h.advance / inter_h.advance
    return AffineTransform(scale_x=scale_x, scale_y=scale_y, translate_y=translate_y)


def transform_glyph(glyph: GlyphMeasurements, transform: AffineTransform) -> GlyphMeasurements:
    bounds = None
    if glyph.bounds is not None:
        xmin, ymin, xmax, ymax = glyph.bounds
        bounds = (
            xmin * transform.scale_x,
            ymin * transform.scale_y + transform.translate_y,
            xmax * transform.scale_x,
            ymax * transform.scale_y + transform.translate_y,
        )
    return GlyphMeasurements(
        bounds=bounds,
        advance=glyph.advance * transform.scale_x,
        lsb=glyph.lsb * transform.scale_x,
    )


def glyph_residual_units(
    pretendard: GlyphMeasurements,
    inter: GlyphMeasurements,
    transform: AffineTransform,
    reference_upm: int,
) -> int:
    transformed = transform_glyph(inter, transform)
    residuals = [
        abs(pretendard.advance - transformed.advance),
        abs(pretendard.lsb - transformed.lsb),
    ]
    if pretendard.bounds is not None and transformed.bounds is not None:
        residuals.extend(
            abs(expected - actual)
            for expected, actual in zip(pretendard.bounds, transformed.bounds)
        )
    return round(max(residuals) * reference_upm) if residuals else 0


def analyze_weight(
    spec: WeightSpec,
    pretendard_path: Path,
    inter_path: Path,
    tolerance_units: int,
) -> dict[str, object]:
    pretendard = read_measurements(pretendard_path)
    inter = read_measurements(inter_path)
    transform = compute_transform(pretendard, inter)
    reference_upm = pretendard.upm
    residuals = {}
    for label in REFERENCE_GLYPHS:
        if label not in pretendard.glyphs or label not in inter.glyphs:
            continue
        residuals[label] = glyph_residual_units(
            pretendard.glyphs[label],
            inter.glyphs[label],
            transform,
            reference_upm,
        )

    modified = sorted(
        label for label, residual in residuals.items() if residual > tolerance_units
    )
    return {
        "pretendard_source": pretendard_path.stem,
        "inter_source": inter_path.stem,
        "pretendard_upm": pretendard.upm,
        "inter_upm": inter.upm,
        "scale_x": transform.scale_x,
        "scale_y": transform.scale_y,
        "translate_y": transform.translate_y,
        "residuals_units": residuals,
        "modified_in_pretendard": modified,
    }


def oversized_residuals(report: dict[str, object], tolerance_units: int) -> dict[str, dict[str, int]]:
    oversized: dict[str, dict[str, int]] = {}
    weights = report.get("weights", {})
    if not isinstance(weights, dict):
        return oversized
    for weight, weight_report in weights.items():
        if not isinstance(weight_report, dict):
            continue
        residuals = weight_report.get("residuals_units", {})
        if not isinstance(residuals, dict):
            continue
        large = {
            glyph: residual
            for glyph, residual in sorted(residuals.items())
            if int(residual) > tolerance_units
        }
        if large:
            oversized[str(weight)] = large
    return dict(sorted(oversized.items()))


def main() -> None:
    args = build_parser().parse_args()
    pretendard_dir = Path(args.pretendard_dir)
    inter_dir = Path(args.inter_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    weights = {}
    for spec in WEIGHT_SPECS:
        pretendard_path = find_font_file(pretendard_dir, spec.pretendard_stem)
        inter_path = find_font_file(inter_dir, spec.inter_stem)
        weights[spec.style] = analyze_weight(
            spec,
            pretendard_path,
            inter_path,
            args.tolerance_units,
        )
        max_residual = max(weights[spec.style]["residuals_units"].values() or [0])
        print(
            f"{spec.style}: scale_x={weights[spec.style]['scale_x']:.6f} "
            f"scale_y={weights[spec.style]['scale_y']:.6f} "
            f"translate_y={weights[spec.style]['translate_y']:.6f} "
            f"max_residual={max_residual}"
        )

    report = {
        "tolerance_units": args.tolerance_units,
        "reference_glyphs": list(REFERENCE_GLYPHS),
        "weights": weights,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    large_residuals = oversized_residuals(report, args.tolerance_units)
    if large_residuals and not args.allow_large_residuals:
        print(
            "Residuals exceed tolerance; inspect mapping_report.json or pin a "
            "matching Inter release before building."
        )
        for weight, residuals in large_residuals.items():
            glyphs = ", ".join(f"{glyph}={value}" for glyph, value in residuals.items())
            print(f"{weight}: {glyphs}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
