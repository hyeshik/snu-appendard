# SNU Appendard v0.6.1

SNU Appendard 0.6.1 is a license-metadata hardening release. It does not change
glyph outlines, metrics, kerning, weight assignments, or family naming.

## Copyright and license changes

- The main license now preserves Pretendard's original copyright statement and
  its `Reserved Font Name Pretendard` declaration verbatim.
- Every OTF carries the Pretendard RFN declaration, the Inter copyright, and
  the SNU Appendard modification copyright in OpenType name ID 0.
- OpenType name ID 13 identifies the SIL Open Font License 1.1 and records that
  the Pretendard RFN applies to the upstream Pretendard Font Software. Name ID
  14 links to the official OFL site.
- `OS/2.fsType` is normalized to `0` so the fonts advertise installable
  embedding instead of inheriting a restriction that conflicts with the OFL.
- Automated tests require the upstream RFN in copyright and license metadata
  while rejecting `Pretendard` from the user-facing SNU Appendard family,
  full, PostScript, typographic-family, and compatible-full names.

Preserving an upstream RFN declaration and using it as a derivative family name
are separate requirements: the declaration remains in the license metadata,
while the distributed family continues to use `SNU Appendard` / `SNUAppendard`.

## Distribution

The release asset is `SNUAppendard-0.6.1.zip`. Its flat archive root contains
18 static OTF files plus `LICENSE.txt`, `LICENSE-Inter.txt`, and
`LICENSE-Pretendard.txt`. Specimens, source fonts, and project files are not
included.

Every font reports `Version 0.6.1` in OpenType name ID 5 and `0.601` in
`head.fontRevision`.
