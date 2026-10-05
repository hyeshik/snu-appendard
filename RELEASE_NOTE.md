# SNU Appendard 0.6.4

Improve compatibility with custom-font converters that require the conventional
PostScript glyph name for U+0020 SPACE.

- Convert the one-dictionary CID-keyed CFF output to name-keyed CFF after all
  outline, spacing, and baseline processing is complete.
- Name U+0020 `space` while preserving its GID, advance width, cmap mappings,
  outlines, OpenType layout references, and U+00A0 alias.
- Verify the normalized CFF structure across all 18 upright and italic styles.
- Credit Joongi Kim ([@achimnol](https://github.com/achimnol)), who reported
  [issue #1](https://github.com/hyeshik/snu-appendard/issues/1).
- Update font metadata and the distribution package to 0.6.4.

`SNUAppendard-0.6.4.zip` contains 18 OTFs and the font licenses.
