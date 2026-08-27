# SNU Appendard

SNU Appendard is a Pretendard-derived OpenType/CFF build that keeps Hangul and
CJK glyphs from Pretendard, imports Inter non-CJK outlines for both upright and
italic styles, and adds true Inter italic forms. Italic styles carry a kerning
guard that keeps sloped letters from colliding with the upright CJK glyphs
around them. Upright styles preserve
Pretendard's advance widths and left sidebearings so spacing stays compatible.
The OTF outputs are generated at UPM 1000 to avoid HP PostScript/PCL interpreters that
incorrectly assume all CFF fonts use 1000 units per em.

This iteration builds static OTF files only. TTF and variable builds are
intentionally deferred.

## Requirements

- FontForge with Python scripting support
- Python 3.10 or newer
- `fontTools` for mapping analysis and output verification
- `make`, `wget`, `jq`, `unzip`, and `zip`
- Typst for specimen generation

On macOS with Homebrew:

```sh
brew install fontforge typst wget jq
python3 -m pip install fonttools
```

On Ubuntu:

```sh
sudo apt-get install fontforge python3-fonttools make wget jq unzip zip
```

Install Typst using your package manager or the official setup action in CI.

## Quick Start

Fetch upstream sources and write the resolved versions to `versions.lock`:

```sh
make sources
```

After `versions.lock` exists, `make sources` reuses the pinned tags. To refresh
to latest releases, run:

```sh
UPDATE_SOURCES=1 make sources
```

To test a specific upstream release:

```sh
INTER_TAG=v3.19 make sources
```

Build the complete OTF family:

```sh
make build
```

Generate the specimen PDF:

```sh
make specimen
```

Create the distribution ZIP:

```sh
make distribution
```

The ZIP has no wrapper directory. Its root contains only the 18 OTF files,
`LICENSE.txt`, `LICENSE-Inter.txt`, and `LICENSE-Pretendard.txt`; the specimen,
README, release notes, and other project files are not distributed.

Create and verify a GitHub release package:

```sh
make release
```

Run the unit tests:

```sh
make test
```

Remove generated artifacts:

```sh
make clean
make distclean
```

## Output

The default build writes 18 files to `dist/otf/`:

- Upright: Thin, ExtraLight, Light, Regular, Medium, SemiBold, Bold,
  ExtraBold, Black
- Italic: ThinItalic, ExtraLightItalic, LightItalic, RegularItalic, MediumItalic,
  SemiBoldItalic, BoldItalic, ExtraBoldItalic, BlackItalic

All outputs use:

- Family name: `SNU Appendard`
- File and PostScript prefix: `SNUAppendard`
- Version name: `0.6.0` (`head.fontRevision == 0.6`)
- OpenType/CFF outlines
- `head.unitsPerEm == 1000`

## Repository Layout

- `scripts/download_sources.sh`: resolves latest Pretendard and Inter release
  assets, downloads them, extracts under `sources/`, and writes
  `versions.lock`
- `scripts/analyze_mapping.py`: derives an Inter to Pretendard Latin transform
  for italic glyph import and writes `build/mapping_report.json`
- `scripts/build_appendard.py`: imports Inter non-CJK outlines into both
  upright and italic styles, preserves Pretendard upright spacing, keeps CJK
  glyphs from Pretendard, scales to UPM 1000, and emits OTFs
- `scripts/fix_metadata.py`: normalizes OpenType name records and style bits
  after FontForge generation
- `scripts/add_italic_cjk_guard.py`: adds the italic-to-upright-CJK collision
  guard to the italic OTFs
- `scripts/make_specimen.sh`: compiles `specimen/specimen.typ`
- `scripts/package_distribution.py`: creates the flat OTF-and-license release ZIP
- `scripts/package_release.py`: builds, verifies, checksums, and stages release
  artifacts under `dist/`
- `tests/`: pure helper tests that run without source font binaries

## Italic CJK Collision Guard

Italic styles mix sloped Inter outlines with upright Pretendard CJK glyphs. Inter
Italic carries ink outside the advance on both sides of a letter, so a letter
placed directly against an upright glyph can overlap it. Both orders collide,
and both are specific to the italics: the same pairs clear in the upright
styles.

| pair | upright | italic, unguarded | italic, guarded |
| ---- | ------- | ----------------- | --------------- |
| `f가` | +32 | -20 | +35 |
| `f파` | +15 | -37 | +38 |
| `다f` | +29 | -69 | +31 |
| `다j` | -10 | -76 | +34 |

`make build` therefore runs `scripts/add_italic_cjk_guard.py` over the generated
OTFs. It buckets the italic glyphs by how far their ink passes the advance and
the upright glyphs by their side bearings, then adds a class-based GPOS pair
positioning lookup to each `kern` feature that widens only the colliding pairs.
Upright fonts are skipped.

Because lookups in one feature accumulate rather than override, the guard also
has to account for the kerning the sources already apply. Pretendard and Inter
kern roughly 38,000 of these cross-script pairs, most of them negatively, so a
guard sized from outlines alone gets partly cancelled: `Ὺ》` needs 150 units but
nets only 89 once upstream kerning has taken its 61 back. The existing
adjustment for every cross-script pair is therefore read out of the font and
folded into the requirement, and each class cell is sized for its least
favourable member.

Properties worth knowing:

- The guard is kerning, so it inserts no space glyph and creates no line-break
  opportunity.
- Pairs that already keep the clearance are untouched, as is Latin-internal
  kerning.
- Re-running the script replaces its own previous lookup instead of stacking a
  second one, so it is safe to apply repeatedly.
- The lookup sets `IgnoreMarks`, matching the kern lookups Pretendard and Inter
  already ship, so a combining mark between a letter and a CJK glyph does not
  hide the pair.
- Combining marks and other zero-advance glyphs take no part in the guard. They
  are positioned by mark attachment, and adding advance to them would displace
  the following glyph by the mark's whole bounding box.
- Pretendard's private-use glyphs are skipped as well. They are not CJK text and
  several draw a full-width form behind an advance of one or two units, so their
  metrics do not describe spacing.
- Clearance is measured from bounding boxes rather than per-outline ink, so a few
  pairs whose ink never overlaps vertically are widened too.
- Guard classes are geometry buckets, not exact per-pair values. Where one cell
  mixes pairs with different upstream kerning, the cell follows its worst member,
  so a few pairs end up slightly wider than the clearance strictly requires.
  Splitting classes finely enough to avoid that would multiply the class matrix
  beyond a usable size.

Change the target clearance, in font units at UPM 1000, with:

```sh
make build GUARD_CLEARANCE=40
```

Applications that shape Latin and CJK as separate runs may still need an
equivalent typesetting boundary rule, because the pair never reaches the shaper.

## Reproducibility Notes

The source fonts and generated outputs are not tracked. `versions.lock` records
the upstream release tags and asset URLs used by the most recent source fetch.
If a newer Inter release no longer matches Pretendard's embedded Latin metrics,
pin the matching Inter release by editing `versions.lock` or passing release
environment overrides to `scripts/download_sources.sh`.

`scripts/analyze_mapping.py` reports reference glyph residuals so Inter version
skew is visible. The Makefile allows large residuals because the transform is
used to size and position imported Inter outlines, while upright advances and
left sidebearings stay compatible with Pretendard and CJK glyphs remain from
Pretendard.

SNU Appendard does not use the reserved upstream family names. See `NOTICE` for
attribution and modification details.
