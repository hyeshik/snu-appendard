# SNU Appendard 0.6.3

Apply the approved macOS system-font sizing and baseline fit to all 18 upright
and italic styles, keeping the SNU Appendard family and file names.

- Scale Hangul and Jamo uniformly by 1.007151371 and raise them 9.432657926 units.
- Scale Latin and other glyphs uniformly by 0.987723485, including advances,
  kerning, mark anchors, and hint zones.
- Set line metrics to 952 / −241 / 0, enable USE_TYPO_METRICS, and add a Roman
  baseline at zero while retaining safe Windows clipping bounds.
- Preserve character coverage, substitutions, style linking, and integer CFF
  coordinates; check every generated glyph before packaging.
- Update font metadata and the distribution package to 0.6.3.

`SNUAppendard-0.6.3.zip` contains 18 OTFs and the font licenses.
