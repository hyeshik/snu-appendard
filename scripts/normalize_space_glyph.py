"""Give U+0020 its conventional CFF glyph name without changing glyph IDs."""
from __future__ import annotations

import os
from pathlib import Path

from fontTools.merge.cmap import renameCFFCharStrings
from fontTools.ttLib import TTFont


SPACE_CODEPOINT = 0x20
CID_TOP_DICT_KEYS = (
    "ROS",
    "CIDFontVersion",
    "CIDFontRevision",
    "CIDFontType",
    "CIDCount",
    "UIDBase",
    "FDSelect",
    "FDArray",
)


def renamed_space_glyph_order(
    glyph_order: list[str], cmap: dict[int, str]
) -> tuple[list[str], str, int]:
    old_name = cmap.get(SPACE_CODEPOINT)
    if old_name is None:
        raise ValueError("The font does not map U+0020 SPACE")
    if old_name == "space":
        return list(glyph_order), old_name, glyph_order.index(old_name)
    if "space" in glyph_order:
        raise ValueError("The font already has another glyph named 'space'")

    space_gid = glyph_order.index(old_name)
    new_order = list(glyph_order)
    new_order[space_gid] = "space"
    return new_order, old_name, space_gid


def normalize_space_glyph(path: Path) -> tuple[str, int]:
    """Convert the one-FD CID CFF to name-keyed CFF and name U+0020 ``space``.

    The glyph order is installed before cmap and layout tables are decompiled,
    so their glyph-ID references retain exactly the same numeric values.
    """
    path = Path(path)
    with TTFont(path, recalcTimestamp=False) as probe:
        glyph_order = probe.getGlyphOrder()
        new_order, old_name, space_gid = renamed_space_glyph_order(
            glyph_order, probe.getBestCmap() or {}
        )
    if old_name == "space":
        return old_name, space_gid

    font = TTFont(path, recalcTimestamp=False)
    temporary_path = path.with_suffix(path.suffix + ".space-tmp")
    try:
        font.setGlyphOrder(new_order)
        if "CFF " not in font:
            raise ValueError("The font has no CFF table")
        cff_table = font["CFF "]
        top_dict = cff_table.cff.topDictIndex[0]
        if not hasattr(top_dict, "ROS"):
            raise ValueError("Expected a CID-keyed CFF font")
        if not hasattr(top_dict, "FDArray") or len(top_dict.FDArray) != 1:
            count = len(top_dict.FDArray) if hasattr(top_dict, "FDArray") else 0
            raise ValueError(f"Expected one CFF font dictionary, found {count}")

        renameCFFCharStrings(None, new_order, cff_table)
        private_dict = top_dict.FDArray[0].Private

        # Load every charstring while its original FD selection is available.
        # The single Private dict and its local subroutines are then reused.
        for glyph_name in new_order:
            top_dict.CharStrings[glyph_name]

        top_dict.Private = private_dict
        for name in CID_TOP_DICT_KEYS:
            top_dict.rawDict.pop(name, None)
            top_dict.__dict__.pop(name, None)
        font.save(temporary_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        font.close()

    try:
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return old_name, space_gid
