# SNU Appendard v0.6.0

Spacing release of SNU Appendard — a Pretendard-derived OpenType/CFF font family that pairs Pretendard's Hangul and CJK glyphs with Inter's Latin outlines, including true Inter italic forms.

## Highlights

- **Italic CJK collision guard**: Italic styles no longer let sloped letters overlap the upright CJK glyphs next to them. Inter Italic carries ink outside the advance on both sides of a letter, so pairs such as `f가` and `다f` used to overlap by 20 to 76 units. Every italic now carries a generated kerning lookup that widens only the colliding pairs, in both orders, while leaving everything that already cleared untouched. See the README for the mechanism and its limits.
- **Hybrid design**: Hangul and CJK glyphs from Pretendard 1.3.9; non-CJK outlines from Inter 4.1 for both upright and italic styles.
- **True italics**: Imports authentic Inter italic forms instead of synthesizing slants from the upright.
- **Pretendard-compatible spacing**: Upright styles preserve Pretendard's advance widths and left sidebearings, so existing layouts stay visually stable.
- **CJK-context symbols fixed**: Enclosed alphanumerics, dingbat circled digits, enclosing combining marks, and private-use glyphs now remain from Pretendard so symbols such as `①`, `⓪`, `➀`, and `🄰` keep their intended visual width.
- **HP-safe UPM**: OTF outputs are generated at `unitsPerEm == 1000` to avoid HP PostScript/PCL interpreters that misread non-1000 CFF fonts.
- **Renamed family**: Distributed as `SNU Appendard` / `SNUAppendard`; reserved upstream names are not used.

## What's in the build

The release ZIP is `SNUAppendard-0.6.0.zip`. Its root contains 18 static OTF
files and the SNU Appendard, Inter, and Pretendard license texts:

- **Upright**: Thin, ExtraLight, Light, Regular, Medium, SemiBold, Bold, ExtraBold, Black
- **Italic**: ThinItalic, ExtraLightItalic, LightItalic, RegularItalic, MediumItalic, SemiBoldItalic, BoldItalic, ExtraBoldItalic, BlackItalic

TTF and variable builds are intentionally deferred for this iteration.

Every font reports `Version 0.6.0` in OpenType name ID 5 and `0.6` in the
numeric `head.fontRevision` field. The release file is
`SNUAppendard-0.6.0.zip`, while the git tag is `v0.6.0`.

## Upstream sources

| Project | Tag | Author |
|---|---|---|
| Pretendard | v1.3.9 | Hyung-jin Kil and contributors |
| Inter | v4.1 | Rasmus Andersson and contributors |

Source tags and asset URLs are pinned in `versions.lock` for reproducibility.

## Build pipeline

- `scripts/download_sources.sh` — resolves and pins upstream releases
- `scripts/analyze_mapping.py` — derives the Inter→Pretendard Latin transform
- `scripts/build_appendard.py` — imports Inter outlines, preserves upright spacing, scales to UPM 1000, emits OTFs
- `scripts/fix_metadata.py` — normalizes OpenType name records and style bits
- `scripts/add_italic_cjk_guard.py` — adds the italic-to-upright-CJK collision guard
- `scripts/make_specimen.sh` and `scripts/package_distribution.py` — specimen PDF and release ZIP

A `make build` target produces the full family; `make test` runs the helper test suite.

## License

SIL Open Font License 1.1. Upstream copyright notices apply to their respective portions. SNU Appendard is not endorsed by the Pretendard or Inter authors. See `NOTICE` and `LICENSE` for details.
