# SNU Appendard 0.6.2

This release makes integer CFF export an explicit build requirement and adds a
full-glyph coordinate check before packaging, matching the printing safeguards
in the other SNU font families. Appendard was the normally printed control in
the HP M281fdw report; this is preventive build hardening.

- Round CFF outline and hint coordinates at final OTF export.
- Verify every generated glyph uses integer outline coordinates.
- Advance the font metadata and package version to 0.6.2.

Validated all 18 OTFs and the 49-test suite. Glyph order, character mappings,
advance widths, GSUB features, and GPOS positioning match the previous release.

`SNUAppendard-0.6.2.zip` contains 18 OTFs and the font licenses.
