# SNU Appendard — Project Plan

## Background

SNU Appendard is a derivative of Pretendard that uses Hangul and CJK glyphs
from Pretendard and re-imports Latin (and other non-CJK) outlines directly from
Inter, the font Pretendard's Latin glyphs were originally derived from. Upright
and italic non-CJK outlines both come from Inter for consistency, while upright
advance widths and left sidebearings remain compatible with Pretendard.

This project follows the same general pattern as earlier Korean font
derivative projects:

- NanumSquare-derived project (interpolated weights added)
- LINE Seed KR-derived project (interpolated weights + italic added)
- **SNU Appendard** ← Pretendard (this project: italic added)

Two technical issues are addressed simultaneously:

1. **No italic.** Pretendard ships only upright styles. Inter has true italic glyphs (not just slanted obliques — `a`, `f`, `e`, etc. have proper italic structures) for all 9 weights. By re-importing Inter's non-CJK outlines into Pretendard, we naturally inherit the italic axis while keeping upright and italic non-CJK sources consistent. Upright output preserves Pretendard's advances and left sidebearings to avoid text reflow.
2. **HP printer spacing bug.** Pretendard OTF uses UPM=2048, but some HP PostScript/PCL interpreters assume CFF/PostScript-flavored fonts have UPM=1000, which collapses advance widths to ~49% of intended. We build OTF at UPM=1000 to fix this.

This iteration ships **OTF only**. TTF builds are deferred to a later iteration once the OTF pipeline is stable.

Most font manipulation is done with **FontForge** (Python API). `fontTools` is used for tasks that are awkward in FontForge (table-level inspection, metric extraction). Specimen generation uses **Typst**.

## Reference repositories

- `snu-edge-sans` — same overall layout, build via FontForge scripts.
- `snu-sprout-sans` — closer reference: also derives from upstream and adds italic.

Inspect both before starting. Copy directory layout, naming conventions, README structure, license/attribution handling, and Makefile/CI style. Stay consistent with the referenced derivative repositories.

## Repository layout

```
snu-appendard/
├── README.md
├── LICENSE                   # OFL-1.1, inherited from Pretendard and Inter
├── NOTICE                    # attribution + modification statement
├── plan.md                   # this file
├── versions.lock             # pinned upstream versions for reproducibility
├── Makefile                  # entry points: sources, build, specimen, dist, clean
├── scripts/
│   ├── download_sources.sh
│   ├── analyze_mapping.py    # fontTools: derive Inter→Pretendard transform
│   ├── build_appendard.py    # FontForge: import glyphs, scale UPM, output OTF
│   └── make_specimen.sh
├── sources/                  # downloaded upstreams (gitignored)
│   ├── pretendard/
│   └── inter/
├── build/                    # intermediate artifacts (gitignored)
│   ├── mapping_report.json
│   └── diff_*.txt
├── dist/                     # final fonts
│   ├── otf/                  # 18 files, UPM=1000, CFF
│   └── SNUAppendard-vX.Y.Z.zip
├── specimen/
│   ├── specimen.typ          # Typst source
│   └── specimen.pdf          # generated comparison PDF
└── .github/
    └── workflows/
        └── build.yml         # full from-scratch CI
```

## Naming conventions

- Family name: `SNU Appendard`
- Subfamily (style) names follow Pretendard: `Thin`, `ExtraLight`, `Light`, `Regular`, `Medium`, `SemiBold`, `Bold`, `ExtraBold`, `Black`
- Italic styles append `Italic` (e.g., `SNU Appendard Bold Italic`)
- Filenames: `SNUAppendard-Regular.otf`, `SNUAppendard-BoldItalic.otf`, etc.
- PostScript names: `SNUAppendard-Regular`, `SNUAppendard-BoldItalic`, etc.

## Phase 1 — Repository setup

1. Create the repository matching the layout above. Initialize with `LICENSE` (OFL-1.1) and `NOTICE` listing Pretendard (Hyung-jin Kil), Inter (Rasmus Andersson), and stating Hyeshik Chang's modifications. Reserve no font names — OFL-1.1 prohibits using "Pretendard" or "Inter" in the family name of derivatives, which "SNU Appendard" satisfies.
2. Add `.gitignore` excluding `sources/`, `build/`, and `dist/`.
3. Implement `scripts/download_sources.sh`:
   - Resolve the latest Pretendard release tag from `https://api.github.com/repos/orioncactus/pretendard/releases/latest` and download the static OTF + TTF zips.
   - Resolve the latest Inter release tag from `https://api.github.com/repos/rsms/inter/releases/latest` and download the `Inter-N.N.zip` bundle (static + variable TTFs, including italic).
   - Write resolved versions to `versions.lock` for reproducibility.
   - Extract under `sources/pretendard/` and `sources/inter/` respectively.
4. Run the script and confirm the directory structures match what the build scripts expect.

## Phase 2 — Mapping analysis

Goal: derive the affine transformation that Pretendard applied to Inter glyphs when ingesting them, so the *same* transform can be applied to Inter italic glyphs.

`scripts/analyze_mapping.py` (use `fontTools` here — easier than FontForge for table reads). For each Pretendard weight and the corresponding Inter weight:

1. Open `Pretendard-{Weight}.ttf` and `Inter-{Weight}.ttf` via `fontTools.ttLib.TTFont`.
2. Extract from each:
   - `head.unitsPerEm`
   - `OS/2.sCapHeight`, `sxHeight`
   - `hhea.ascent`, `descent`, `lineGap`
   - For reference glyphs `H`, `n`, `o`, `x`, `I`, `A`, `g`, `period`: bounding box (via `fontTools.pens.boundsPen.BoundsPen`), advance width, LSB.
3. Normalize all measurements to em coordinates (divide by UPM). Both fonts use UPM=2048, so the ratio is 1:1 in practice, but the code should handle arbitrary UPM.
4. Compute candidate transforms:
   - **Vertical scale** = Pretendard cap height / Inter cap height (em-normalized)
   - **Vertical translate** = baseline offset such that Pretendard `H` bottom == (Inter `H` bottom × scale_y) + translate_y
   - **Horizontal scale** = Pretendard advance(`H`) / Inter advance(`H`) (em-normalized)
5. Verify the same transform fits all reference glyphs to within tight tolerance (≤4 units at UPM=2048). If a single uniform transform fits, the mapping is clean. If not, log per-glyph residuals — Pretendard may have hand-edited those glyphs.
6. Write `build/mapping_report.json`:
   ```json
   {
     "weights": {
       "Regular": {
         "inter_source": "Inter-Regular",
         "scale_x": 1.0,
         "scale_y": 1.0,
         "translate_y": 0,
         "residuals_units": {"H": 0, "n": 1, "o": 0, ...},
         "modified_in_pretendard": ["W", "w", "I", "l"]
       },
       ...
     }
   }
   ```

Expected outcome: the transform is near-identity (Pretendard's Latin is essentially Inter copied through with a handful of glyph-level edits). If residuals are large or weights map non-1:1 (e.g., Pretendard Bold ≠ Inter Bold), halt and re-examine before proceeding.

## Phase 3 — Build prototype: Regular only

Before scaling to all 9 weights, build one upright + italic pair and validate.

`scripts/build_appendard.py` (FontForge Python), invoked as:

```bash
fontforge -script scripts/build_appendard.py \
  --pretendard sources/pretendard/Pretendard-Regular.ttf \
  --inter sources/inter/Inter-Regular.ttf \
  --inter-italic sources/inter/Inter-Italic.ttf \
  --transform build/mapping_report.json \
  --weight Regular \
  --output build/SNUAppendard-Regular.otf \
  --output-italic build/SNUAppendard-Italic.otf
```

Inside the script:

1. Open Pretendard-Regular as the base font.
2. Identify the set of non-CJK glyphs to replace. Use the cmap: any codepoint outside Hangul (U+1100–U+11FF, U+3130–U+318F, U+A960–U+A97F, U+AC00–U+D7AF, U+D7B0–U+D7FF) and CJK Unified Ideographs / Compatibility blocks. Build the replacement glyph-name list.
3. For each non-CJK glyph in the replacement set:
   - If present in Inter-Regular at the same Unicode codepoint: import its outline from Inter, apply the affine transform from `mapping_report.json`, and replace Pretendard's outline.
   - For upright output, preserve Pretendard's original advance width and left sidebearing to keep spacing compatible.
   - For italic output, set advance widths and sidebearings from transformed Inter italic glyphs.
4. Update font-level metadata:
   - Family name → `SNU Appendard`
   - Style name preserved (`Regular`, etc.)
   - PostScript name → `SNUAppendard-Regular`
   - Version string includes upstream Pretendard + Inter versions and a build timestamp.
   - Copyright field combines OFL attributions + Hyeshik Chang modification notice.
   - `name` table IDs 1, 2, 3, 4, 6, 16, 17 updated consistently.
5. Scale UPM to 1000 to fix the HP printer issue: `font.em = 1000` — FontForge automatically scales all outlines, advance widths, and metrics by 1000/2048 ≈ 0.4883. Re-run autohinting for CFF: `font.autoHint()`.
6. Generate as OpenType (CFF): `font.generate("build/SNUAppendard-Regular.otf", flags=("opentype",))`. Verify the output: `head.unitsPerEm == 1000`, `CFF ` table present, `glyf` table absent.
7. Repeat for italic, starting from a *fresh copy* of Pretendard-Regular (to inherit Hangul) but pulling Latin glyphs from `Inter-Italic.ttf`. Style → `Italic`, PostScript name → `SNUAppendard-Italic`. Set:
   - `OS/2.fsSelection` italic bit (bit 0)
   - `head.macStyle` italic bit (bit 1)
   - `post.italicAngle` to Inter's italic angle (~−10°; copy verbatim from Inter)
   - `hhea.caretSlopeRise` / `caretSlopeRun` consistent with the italic angle
8. Hangul and CJK glyphs are inherited from Pretendard untouched in both upright and italic builds. (Italic Hangul does not exist as a tradition; using upright Hangul in the italic font is the standard approach for CJK italic typefaces.)

## Phase 4 — Validation of prototype

After Phase 3:

1. **Scale and import check.** For non-CJK glyphs in `SNUAppendard-Regular.otf` vs the matching Inter source:
   - Convert Inter source coordinates through the Inter-UPM → Pretendard-UPM conversion, apply the affine transform from `mapping_report.json`, then scale to UPM 1000.
   - Compare representative bounds for Latin glyphs across all weights.
   - Confirm upright advance widths and left sidebearings match Pretendard, while italic advance widths follow Inter italic.
   - Confirm Hangul and CJK glyphs still match Pretendard after the 2048→1000 UPM scaling.
   - If imported non-CJK glyphs are visibly larger than CJK glyphs, verify the source-UPM conversion before checking the affine transform.

2. **Specimen PDF** (see Phase 6 spec) showing Pretendard vs SNU Appendard side-by-side. At a glance: CJK text and upright spacing remain aligned with Pretendard, and non-CJK Inter forms are consistent across upright and italic styles.

If both checks pass, proceed to Phase 5. If they fail, iterate the transform.

## Phase 5 — Build all 9 weights

Loop the build script over all weight pairs. Default mapping (override per `mapping_report.json` if Phase 2 found differences):

| SNU Appendard weight | Inter (upright) | Inter (italic) |
|---|---|---|
| Thin (100) | Inter-Thin | Inter-ThinItalic |
| ExtraLight (200) | Inter-ExtraLight | Inter-ExtraLightItalic |
| Light (300) | Inter-Light | Inter-LightItalic |
| Regular (400) | Inter-Regular | Inter-Italic |
| Medium (500) | Inter-Medium | Inter-MediumItalic |
| SemiBold (600) | Inter-SemiBold | Inter-SemiBoldItalic |
| Bold (700) | Inter-Bold | Inter-BoldItalic |
| ExtraBold (800) | Inter-ExtraBold | Inter-ExtraBoldItalic |
| Black (900) | Inter-Black | Inter-BlackItalic |

Output → `dist/otf/` (18 files: 9 upright + 9 italic, UPM=1000, CFF).

Run the Phase 4 outline diff for every weight, not just Regular. The set of "modified" glyphs should be consistent across weights.

Note on UPM scaling: 2048 → 1000 with integer rounding loses sub-unit precision. Stem widths may shift by ±1 unit. This is acceptable for body text and corrects the HP printer issue. If precision loss is visible at display sizes, consider keeping fractional coordinates in the CFF (CFF supports them).

## Phase 6 — Specimen PDF

`specimen/specimen.typ` (Typst):

- **Page 1 — Cover.** Title, version, brief description, build date, upstream versions.
- **Page 2–3 — Weight grid.** Pretendard vs SNU Appendard at all 9 weights, both upright and italic. Same string in each cell. Visual diffs jump out immediately.
- **Page 4 — Body text.** Mixed Korean–English paragraphs at 10pt, 11pt, 12pt. Three samples: technical/academic, casual prose, numerals + punctuation. Pretendard above each, SNU Appendard below.
- **Page 5 — Italic showcase.** Bibliographic entries, scientific names (e.g., *E. coli*, *Drosophila melanogaster*), emphasized words in running Korean–English prose. Pretendard left (will fall back to upright since it has no italic), SNU Appendard right.
- **Page 6 — Glyph table.** All non-CJK glyphs at one weight (Regular), upright and italic, in a grid with codepoints labeled.
- **Page 7 — Print-test patterns.** A page designed to expose the HP printer spacing bug. Long lines of mixed-width characters, tabular figures, repeated common words. Set the same content twice: once in original Pretendard OTF (UPM=2048, exhibits the bug) and once in SNU Appendard OTF (UPM=1000, fixed). A printout from the HP printer makes the spacing collapse on the Pretendard side and the correct rendering on the SNU Appendard side visible side-by-side.

`scripts/make_specimen.sh`:

1. Symlink/copy `dist/otf/*.otf` and the original `sources/pretendard/*.otf` (for the print-test page) into a temp dir.
2. Run `typst compile specimen/specimen.typ specimen/specimen.pdf --font-path <tempdir>`.

## Phase 7 — Iterate

Review the specimen PDF carefully. Likely follow-ups:

- Vertical metrics: check that italic descenders aren't cramped against Hangul. Adjust `OS/2.usWinDescent` if needed.
- `OS/2` settings: `fsSelection`, `usWinAscent/Descent`, `sTypoAscender/Descender`, `hhea.ascent/descent/lineGap` — keep Pretendard-compatible vertical metrics; toggle the italic bit for italic styles.
- `name` table: confirm all platform/encoding/language combos populated correctly (Mac Roman, Windows Unicode, optionally Korean).
- Italic angle consistency across weights.
- Print one OTF page from the HP printer to confirm the spacing bug is resolved.

Re-run the full build until specimen looks clean, CJK parity with Pretendard is
confirmed, and imported Inter non-CJK glyphs have the intended normalized size.

## Phase 8 — Automation: from-scratch reproducible build

Once the manual pipeline produces correct output, formalize it into a single reproducible workflow.

`Makefile` targets:

- `make sources` → runs `scripts/download_sources.sh`
- `make build` → produces all OTFs in `dist/otf/` (depends on `sources`)
- `make specimen` → produces `specimen/specimen.pdf` (depends on `build`)
- `make dist` → produces `dist/SNUAppendard-vX.Y.Z.zip` containing OTFs, LICENSE, NOTICE, README, and the specimen PDF
- `make clean` → removes `build/` and `dist/`
- `make distclean` → also removes `sources/`

`.github/workflows/build.yml`:

- Triggers: push to `main`, manual dispatch, version tags (`v*`).
- Steps:
  1. Checkout
  2. Install: `fontforge` (with python3 bindings), `python3-fonttools`, `typst`, `unzip`, `wget`, `jq`
  3. `make distclean && make sources && make build && make specimen && make dist`
  4. Upload `dist/*.zip` and `specimen/specimen.pdf` as build artifacts.
  5. On tagged release: also upload `dist/*.zip` as a GitHub release asset.

The CI must succeed *from a clean checkout with no local artifacts*. This is the acceptance test for Phase 8.

## Acceptance criteria

- [ ] `make distclean && make dist` succeeds locally.
- [ ] CI pipeline succeeds from a clean checkout.
- [ ] Output zip contains 18 OTFs (9 weights × 2 styles: upright + italic).
- [ ] All OTFs have `head.unitsPerEm == 1000` and CFF outlines.
- [ ] For each SNU Appendard OTF, imported non-CJK glyphs match the transformed Inter source at UPM 1000.
- [ ] CJK (Hangul) glyphs are preserved from upstream Pretendard (modulo the 2048→1000 UPM scaling).
- [ ] Italic styles render correctly with proper italic forms for `a`, `f`, `e`, etc.
- [ ] Specimen PDF compiles and shows clean side-by-side comparisons.
- [ ] HP printer test print: SNU Appendard OTF prints with correct (not collapsed) spacing.

## Open questions and risks

- **Inter version skew.** Inter v4 changed metrics from v3. Confirm the Pretendard release we use was built against the Inter version we download. If Pretendard tracks an older Inter, pin Inter to the matching version in `versions.lock` rather than always grabbing latest.
- **Glyph coverage.** Pretendard JP and Pretendard Std are out of scope. This project targets the main `Pretendard` family only.
- **Variable font.** Deferred. Static fonts only in v1. A variable build (with `wght` + `ital` axes) can be added once the static pipeline is stable.
- **TTF builds.** Deferred to a future iteration. Adding TTF requires preserving UPM=2048 (the TrueType convention), so the build script will need a branch: build at UPM=2048 → emit TTF, then scale to 1000 → emit OTF. Once the OTF-only pipeline is validated, this fork is straightforward.
- **Hinting quality.** FontForge's auto-hinting for CFF (`font.autoHint()`) is adequate for screen rendering and printing. Pretendard's original hinting cannot be reused since UPM has changed; rely on autohint.
- **License compliance.** OFL-1.1 prohibits using "Pretendard" or "Inter" in the family name of derivatives. "SNU Appendard" satisfies this. Include the original OFL notices verbatim in `LICENSE` and the modification statement in `NOTICE`.
- **Trademark.** "Pretendard" and "Inter" are trademarks of their respective authors per their LICENSE files. The `NOTICE` should clearly state that SNU Appendard is a derivative work and not endorsed by the original authors.
