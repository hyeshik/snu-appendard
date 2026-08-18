#!/usr/bin/env python3
"""Add italic-to-upright-CJK optical guards to generated SNU Appendard OTFs.

Italic styles take their non-CJK outlines from Inter Italic while Hangul, CJK,
and the enclosed-symbol ranges stay upright from Pretendard. Inter Italic is a
true italic whose sloped letters carry ink outside their own advance on both
sides, so a letter set directly against an upright glyph can overlap it:

    f가   61 unit right overhang against a 41 unit side bearing  -> -20 units
    다f   80 unit left overhang against an 11 unit side bearing  -> -69 units

Both directions are guarded here, because both are introduced by the italic
outlines: the same pairs clear comfortably in the upright styles.

The fix is a class-based GPOS pair positioning lookup added to every ``kern``
feature, so it inserts no space glyph and creates no line-break opportunity.

Pretendard and Inter already kern tens of thousands of these cross-script pairs,
often negatively, and lookups in one feature accumulate rather than override. A
guard sized from outlines alone is therefore partly cancelled: the pair
``\u1ffa\u300b`` needs 150 units but nets only 89 once upstream kerning has taken
its 61 back. The existing adjustment for every cross-script pair is read out of
the font first and folded into the requirement.
"""
from __future__ import annotations

import argparse
import math
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from fontTools.otlLib.builder import (
    buildLookup,
    buildPairPosClassesSubtable,
    buildValue,
)
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from build_appendard import (
    is_cjk_codepoint,
    is_cjk_context_symbol,
    should_keep_pretendard_codepoint,
)


DEFAULT_CLEARANCE = 30
DEFAULT_BUCKET_SIZE = 5
# Matches the flag on the kern lookups Pretendard and Inter already ship, so a
# combining mark between a letter and a CJK glyph does not hide the pair.
IGNORE_MARKS_FLAG = 0x08


class GuardStats(NamedTuple):
    replaced_previous_guard: bool
    existing_adjusted_pairs: int
    slanted_glyphs: int
    upright_glyphs: int
    forward_pairs: int
    reverse_pairs: int
    guard_min: int
    guard_max: int
    lookup_index: int


class GlyphSides(NamedTuple):
    """Per-glyph geometry, measured outward from the advance box."""

    right_overhang: float
    left_overhang: float
    right_side_bearing: float
    left_side_bearing: float


def round_up(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def round_down(value: float, step: int) -> int:
    return int(math.floor(value / step) * step)


def guard_units(
    *,
    overhang: float,
    side_bearing: float,
    existing_adjustment: float = 0,
    clearance: int = DEFAULT_CLEARANCE,
    bucket_size: int = DEFAULT_BUCKET_SIZE,
) -> int:
    """Advance to add so a pair keeps ``clearance`` units of ink gap.

    ``existing_adjustment`` is what the font's own kerning already does to this
    pair; it is subtracted because our lookup accumulates on top of it rather
    than replacing it. Zero means the pair already clears and keeps its designed
    spacing.
    """
    required = overhang + clearance - side_bearing - existing_adjustment
    if required <= 0:
        return 0
    return round_up(required, bucket_size)


def glyph_sides(glyph_set, hmtx, glyph_name: str) -> GlyphSides | None:
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    if pen.bounds is None:
        return None

    x_min, _, x_max, _ = pen.bounds
    advance_width = hmtx[glyph_name][0]
    return GlyphSides(
        right_overhang=x_max - advance_width,
        left_overhang=-x_min,
        right_side_bearing=advance_width - x_max,
        left_side_bearing=x_min,
    )


def encoded_glyph_codepoints(font: TTFont) -> dict[str, set[int]]:
    codepoints: dict[str, set[int]] = defaultdict(set)
    for codepoint, glyph_name in font.getBestCmap().items():
        codepoints[glyph_name].add(codepoint)
    return codepoints


def participates_in_spacing(codepoints: set[int], advance_width: int) -> bool:
    """Report whether kerning this glyph is meaningful at all.

    Combining marks are placed by mark attachment rather than by advances, and
    Inter contributes several hundred of them with a zero advance. Adding
    XAdvance to a mark would shove the following glyph away by the mark's whole
    bounding box, so marks and other zero-advance glyphs are left out entirely.
    """
    if advance_width <= 0:
        return False
    return not any(
        unicodedata.category(chr(codepoint)).startswith("M")
        for codepoint in codepoints
    )


def guard_side(codepoints: set[int]) -> bool | None:
    """Return True for the upright CJK side, False for the italic side.

    ``None`` means the glyph takes no part in the guard: either it is reachable
    from codepoints on both sides, or it is one of the private-use glyphs
    Pretendard carries for its own composition machinery. Those are not CJK text
    and their metrics do not describe spacing -- several draw a full-width form
    behind an advance of one or two units -- so pairing them would produce
    guards several hundred units wide for glyphs nobody types.
    """
    sides = set()
    for codepoint in codepoints:
        if is_cjk_codepoint(codepoint) or is_cjk_context_symbol(codepoint):
            sides.add(True)
        elif not should_keep_pretendard_codepoint(codepoint):
            sides.add(False)
        else:
            return None
    if len(sides) != 1:
        return None
    return sides.pop()


def kern_lookup_indices(font: TTFont) -> list[int]:
    feature_list = font["GPOS"].table.FeatureList
    if feature_list is None:
        return []
    return sorted(
        {
            index
            for record in feature_list.FeatureRecord
            if record.FeatureTag == "kern"
            for index in record.Feature.LookupListIndex
        }
    )


def pair_position_subtables(lookup):
    if lookup.LookupType == 2:
        yield from lookup.SubTable
        return
    if lookup.LookupType != 9:
        return
    for extension in lookup.SubTable:
        if extension.ExtensionLookupType == 2:
            yield extension.ExtSubTable


def gap_delta(value1, value2) -> int:
    """How much a pair value record widens the ink gap inside the pair.

    Advancing the first glyph or displacing the second one to the right opens
    the gap; displacing the first glyph to the right closes it. ``Value2``'s
    advance only affects the following pair, so it is ignored here.
    """
    delta = 0
    if value1 is not None:
        delta += getattr(value1, "XAdvance", 0) or 0
        delta -= getattr(value1, "XPlacement", 0) or 0
    if value2 is not None:
        delta += getattr(value2, "XPlacement", 0) or 0
    return delta


def find_existing_guard(font: TTFont) -> int | None:
    """Locate a guard this script appended on an earlier run.

    Running twice must not stack, and it must not read its own output back as
    upstream kerning. The guard is recognisable because it is the last lookup in
    the table, the last lookup of every kern feature, and a mark-ignoring pair
    positioning lookup built only from class subtables. If the guess is ever
    wrong the cost is rebuilding an equivalent lookup.
    """
    gpos = font["GPOS"].table
    lookups = gpos.LookupList.Lookup
    if not lookups:
        return None

    candidate = len(lookups) - 1
    kern_indices = [
        list(record.Feature.LookupListIndex)
        for record in gpos.FeatureList.FeatureRecord
        if record.FeatureTag == "kern"
    ]
    if not kern_indices or not all(indices[-1:] == [candidate] for indices in kern_indices):
        return None

    lookup = lookups[candidate]
    if lookup.LookupFlag != IGNORE_MARKS_FLAG:
        return None
    subtables = list(pair_position_subtables(lookup))
    if not subtables or len(subtables) > 2:
        return None
    if any(subtable.Format != 2 for subtable in subtables):
        return None
    return candidate


def drop_lookup(font: TTFont, lookup_index: int) -> None:
    """Remove a trailing lookup and every feature reference to it."""
    gpos = font["GPOS"].table
    if lookup_index != len(gpos.LookupList.Lookup) - 1:
        raise ValueError("Only the last GPOS lookup can be dropped safely.")

    for record in gpos.FeatureList.FeatureRecord:
        feature = record.Feature
        if lookup_index in feature.LookupListIndex:
            feature.LookupListIndex = [
                index for index in feature.LookupListIndex if index != lookup_index
            ]
            feature.LookupCount = len(feature.LookupListIndex)
    del gpos.LookupList.Lookup[lookup_index]
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)


def existing_adjustments(
    font: TTFont,
    side_of: dict[str, bool],
) -> dict[tuple[str, str], int]:
    """Read what the font's own kerning already does to cross-script pairs.

    Only pairs whose members sit on opposite sides of the guard are collected,
    since those are the only ones the guard can touch.
    """
    adjustments: dict[tuple[str, str], int] = {}
    lookups = font["GPOS"].table.LookupList.Lookup

    def record(first: str, second: str, delta: int) -> None:
        if not delta:
            return
        first_side = side_of.get(first)
        second_side = side_of.get(second)
        if first_side is None or second_side is None or first_side == second_side:
            return
        adjustments[(first, second)] = adjustments.get((first, second), 0) + delta

    for index in kern_lookup_indices(font):
        for subtable in pair_position_subtables(lookups[index]):
            if subtable.Format == 1:
                for first, pair_set in zip(subtable.Coverage.glyphs, subtable.PairSet):
                    for pair in pair_set.PairValueRecord:
                        record(
                            first,
                            pair.SecondGlyph,
                            gap_delta(pair.Value1, pair.Value2),
                        )
            elif subtable.Format == 2:
                first_by_class: dict[int, list[str]] = defaultdict(list)
                for glyph in subtable.Coverage.glyphs:
                    if glyph in side_of:
                        first_by_class[subtable.ClassDef1.classDefs.get(glyph, 0)].append(glyph)
                second_by_class: dict[int, list[str]] = defaultdict(list)
                for glyph in side_of:
                    second_by_class[subtable.ClassDef2.classDefs.get(glyph, 0)].append(glyph)

                for first_class, class1_record in enumerate(subtable.Class1Record):
                    firsts = first_by_class.get(first_class)
                    if not firsts:
                        continue
                    for second_class, class2_record in enumerate(class1_record.Class2Record):
                        delta = gap_delta(class2_record.Value1, class2_record.Value2)
                        if not delta:
                            continue
                        for first in firsts:
                            for second in second_by_class.get(second_class, ()):
                                record(first, second, delta)
    return adjustments


def worst_adjustment_per_cell(
    adjustments: dict[tuple[str, str], int],
    first_class_of: dict[str, int],
    second_class_of: dict[str, int],
    class_sizes: dict[tuple[int, int], int],
) -> dict[tuple[int, int], int]:
    """Reduce per-pair adjustments to the worst case within each class cell.

    A cell is sized for its least favourable member, and a cell that still has
    any unkerned member cannot assume better than zero. Guarding cannot be finer
    than this without splitting classes along the upstream kern classes, which
    would multiply the class matrix out of usable size.
    """
    worst: dict[tuple[int, int], int] = {}
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for (first, second), delta in adjustments.items():
        first_class = first_class_of.get(first)
        second_class = second_class_of.get(second)
        if first_class is None or second_class is None:
            continue
        cell = (first_class, second_class)
        counts[cell] += 1
        if cell not in worst or delta < worst[cell]:
            worst[cell] = delta

    for cell, value in list(worst.items()):
        if value > 0 and counts[cell] < class_sizes.get(cell, 0):
            worst[cell] = 0
    return worst


def collect_geometry_classes(
    font: TTFont,
    bucket_size: int,
) -> dict[str, dict[int, tuple[str, ...]]]:
    """Bucket both sides of both pair orders by the geometry that can collide.

    Overhangs round up and side bearings round down, so the guard derived from
    a bucket is never smaller than what any member of that bucket needs.
    """
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    buckets: dict[str, dict[int, list[str]]] = {
        "slanted_right": defaultdict(list),
        "slanted_left": defaultdict(list),
        "upright_left": defaultdict(list),
        "upright_right": defaultdict(list),
    }

    for glyph_name, codepoints in encoded_glyph_codepoints(font).items():
        upright = guard_side(codepoints)
        if upright is None:
            continue
        if not participates_in_spacing(codepoints, hmtx[glyph_name][0]):
            continue
        sides = glyph_sides(glyph_set, hmtx, glyph_name)
        if sides is None:
            continue

        if upright:
            key = round_down(sides.left_side_bearing, bucket_size)
            buckets["upright_left"][key].append(glyph_name)
            key = round_down(sides.right_side_bearing, bucket_size)
            buckets["upright_right"][key].append(glyph_name)
        else:
            key = round_up(sides.right_overhang, bucket_size)
            buckets["slanted_right"][key].append(glyph_name)
            key = round_up(sides.left_overhang, bucket_size)
            buckets["slanted_left"][key].append(glyph_name)

    return {
        name: {key: tuple(sorted(value)) for key, value in bucket.items()}
        for name, bucket in buckets.items()
    }


def guarded_pairs(
    first_classes: dict[int, tuple[str, ...]],
    second_classes: dict[int, tuple[str, ...]],
    *,
    overhang_first: bool,
    clearance: int,
    bucket_size: int,
    worst_adjustments: dict[tuple[int, int], int] | None = None,
) -> dict[tuple[tuple[str, ...], tuple[str, ...]], int]:
    """Build the guard value for each colliding class pair.

    ``overhang_first`` selects the pair order: the overhanging italic glyph is
    the first member going into upright CJK, and the second member coming out of
    it. Either way the advance is added to the first member, which is what
    widens the gap between the two.
    """
    worst_adjustments = worst_adjustments or {}
    pairs = {}
    for first_key, first_glyphs in first_classes.items():
        for second_key, second_glyphs in second_classes.items():
            overhang, side_bearing = (
                (first_key, second_key) if overhang_first else (second_key, first_key)
            )
            units = guard_units(
                overhang=overhang,
                side_bearing=side_bearing,
                existing_adjustment=worst_adjustments.get((first_key, second_key), 0),
                clearance=clearance,
                bucket_size=bucket_size,
            )
            if units:
                pairs[(first_glyphs, second_glyphs)] = units
    return pairs


def class_index(classes: dict[int, tuple[str, ...]]) -> dict[str, int]:
    return {glyph: key for key, glyphs in classes.items() for glyph in glyphs}


def cell_sizes(
    first_classes: dict[int, tuple[str, ...]],
    second_classes: dict[int, tuple[str, ...]],
) -> dict[tuple[int, int], int]:
    return {
        (first_key, second_key): len(first_glyphs) * len(second_glyphs)
        for first_key, first_glyphs in first_classes.items()
        for second_key, second_glyphs in second_classes.items()
    }


def append_guard_lookup(
    font: TTFont,
    *,
    clearance: int = DEFAULT_CLEARANCE,
    bucket_size: int = DEFAULT_BUCKET_SIZE,
) -> GuardStats:
    if "GPOS" not in font:
        raise ValueError("The input font has no GPOS table.")
    if font["post"].italicAngle == 0:
        raise ValueError("The input font is not marked as italic.")

    previous_guard = find_existing_guard(font)
    if previous_guard is not None:
        drop_lookup(font, previous_guard)

    buckets = collect_geometry_classes(font, bucket_size)
    if not buckets["slanted_right"]:
        raise ValueError("The input font has no Inter-sourced glyphs.")
    if not buckets["upright_left"]:
        raise ValueError("The input font has no upright CJK glyphs.")

    side_of = {
        glyph: True
        for glyphs in buckets["upright_left"].values()
        for glyph in glyphs
    }
    side_of.update(
        {glyph: False for glyphs in buckets["slanted_right"].values() for glyph in glyphs}
    )
    adjustments = existing_adjustments(font, side_of)

    forward = guarded_pairs(
        buckets["slanted_right"],
        buckets["upright_left"],
        overhang_first=True,
        clearance=clearance,
        bucket_size=bucket_size,
        worst_adjustments=worst_adjustment_per_cell(
            adjustments,
            class_index(buckets["slanted_right"]),
            class_index(buckets["upright_left"]),
            cell_sizes(buckets["slanted_right"], buckets["upright_left"]),
        ),
    )
    reverse = guarded_pairs(
        buckets["upright_right"],
        buckets["slanted_left"],
        overhang_first=False,
        clearance=clearance,
        bucket_size=bucket_size,
        worst_adjustments=worst_adjustment_per_cell(
            adjustments,
            class_index(buckets["upright_right"]),
            class_index(buckets["slanted_left"]),
            cell_sizes(buckets["upright_right"], buckets["slanted_left"]),
        ),
    )
    if not forward and not reverse:
        raise ValueError("No italic/upright pair needs a guard.")

    empty_value = buildValue({})
    reverse_glyph_map = font.getReverseGlyphMap()
    subtables = []
    for pairs in (forward, reverse):
        if not pairs:
            continue
        subtables.append(
            buildPairPosClassesSubtable(
                {
                    classes: (buildValue({"XAdvance": units}), empty_value)
                    for classes, units in pairs.items()
                },
                reverse_glyph_map,
            )
        )

    # One lookup is enough for both orders: a pair can only ever match the
    # subtable whose first-glyph coverage it falls in, and those are disjoint.
    lookup = buildLookup(subtables, flags=IGNORE_MARKS_FLAG)
    gpos = font["GPOS"].table
    lookup_index = len(gpos.LookupList.Lookup)
    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)

    kern_features = [
        record.Feature
        for record in gpos.FeatureList.FeatureRecord
        if record.FeatureTag == "kern"
    ]
    if not kern_features:
        raise ValueError("The input font has no GPOS kern feature.")
    for feature in kern_features:
        feature.LookupListIndex.append(lookup_index)
        feature.LookupCount = len(feature.LookupListIndex)

    values = list(forward.values()) + list(reverse.values())
    return GuardStats(
        replaced_previous_guard=previous_guard is not None,
        existing_adjusted_pairs=len(adjustments),
        slanted_glyphs=sum(map(len, buckets["slanted_right"].values())),
        upright_glyphs=sum(map(len, buckets["upright_left"].values())),
        forward_pairs=len(forward),
        reverse_pairs=len(reverse),
        guard_min=min(values),
        guard_max=max(values),
        lookup_index=lookup_index,
    )


def guard_font(
    path: Path,
    *,
    clearance: int = DEFAULT_CLEARANCE,
    bucket_size: int = DEFAULT_BUCKET_SIZE,
) -> GuardStats | None:
    """Guard one OTF in place. Returns ``None`` for upright fonts."""
    font = TTFont(str(path))
    temporary_path = path.with_suffix(path.suffix + ".guard-tmp")
    try:
        if font["post"].italicAngle == 0:
            return None
        stats = append_guard_lookup(
            font,
            clearance=clearance,
            bucket_size=bucket_size,
        )
        font.save(str(temporary_path))
    finally:
        font.close()

    temporary_path.replace(path)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Add non-breaking italic-to-upright-CJK optical guards to built "
            "SNU Appendard OTFs. Upright fonts are skipped."
        )
    )
    parser.add_argument("--font", action="append")
    parser.add_argument("--input-dir", default="dist/otf")
    parser.add_argument("--clearance", type=int, default=DEFAULT_CLEARANCE)
    parser.add_argument("--bucket-size", type=int, default=DEFAULT_BUCKET_SIZE)
    return parser


def input_paths(args) -> list[Path]:
    if args.font:
        return [Path(font_path) for font_path in args.font]
    return sorted(Path(args.input_dir).glob("SNUAppendard-*.otf"))


def main() -> None:
    args = build_parser().parse_args()
    paths = input_paths(args)
    if not paths:
        raise SystemExit("No SNU Appendard OTFs found to guard.")

    for path in paths:
        stats = guard_font(
            path,
            clearance=args.clearance,
            bucket_size=args.bucket_size,
        )
        if stats is None:
            print(f"{path}: upright, no guard needed")
            continue
        print(
            f"{path}: slanted_glyphs={stats.slanted_glyphs}, "
            f"upstream_kerned_pairs={stats.existing_adjusted_pairs}, "
            f"upright_glyphs={stats.upright_glyphs}, "
            f"forward_pairs={stats.forward_pairs}, "
            f"reverse_pairs={stats.reverse_pairs}, "
            f"guard_range={stats.guard_min}..{stats.guard_max}, "
            f"replaced_previous={stats.replaced_previous_guard}, "
            f"lookup_index={stats.lookup_index}"
        )


if __name__ == "__main__":
    main()
