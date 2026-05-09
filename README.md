# SNU Appendard

SNU Appendard is a Pretendard-derived OpenType/CFF build that keeps Hangul and
CJK glyphs from Pretendard, imports Inter non-CJK outlines for both upright and
italic styles, and adds true Inter italic forms. Upright styles preserve
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
make dist
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
- Italic: ThinItalic, ExtraLightItalic, LightItalic, Italic, MediumItalic,
  SemiBoldItalic, BoldItalic, ExtraBoldItalic, BlackItalic

All outputs use:

- Family name: `SNU Appendard`
- File and PostScript prefix: `SNUAppendard`
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
- `scripts/make_specimen.sh`: compiles `specimen/specimen.typ`
- `scripts/package_dist.py`: creates the release ZIP
- `tests/`: pure helper tests that run without source font binaries

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
