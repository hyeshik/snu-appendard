import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
from zipfile import ZipFile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")


def load_module(name, path):
    # Scripts import each other by bare module name, which works because
    # FontForge and python3 both put the script's own directory first on
    # sys.path. Reproduce that here.
    sys.path.insert(0, SCRIPTS)
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(SCRIPTS)


class BuildAppendardContractTests(unittest.TestCase):
    def test_weight_matrix_and_output_names_match_project_contract(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        self.assertEqual(builder.FAMILY_NAME, "SNU Appendard")
        self.assertEqual(builder.POSTSCRIPT_FAMILY_NAME, "SNUAppendard")
        self.assertEqual(
            [spec.style for spec in builder.WEIGHT_SPECS],
            [
                "Thin",
                "ExtraLight",
                "Light",
                "Regular",
                "Medium",
                "SemiBold",
                "Bold",
                "ExtraBold",
                "Black",
            ],
        )
        self.assertEqual(builder.style_name("Regular", False), "Regular")
        self.assertEqual(builder.style_name("Regular", True), "Italic")
        self.assertEqual(builder.style_name("Bold", True), "Bold Italic")
        self.assertEqual(builder.postscript_style_name("Regular", True), "RegularItalic")
        self.assertEqual(builder.postscript_style_name("Bold", True), "BoldItalic")
        self.assertEqual(
            builder.output_filename("ExtraLight", True),
            "SNUAppendard-ExtraLightItalic.otf",
        )

    def test_replacement_predicate_keeps_cjk_and_hangul_from_pretendard(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        self.assertTrue(builder.should_replace_codepoint(ord("A")))
        self.assertTrue(builder.should_replace_codepoint(0x03A9))
        self.assertTrue(builder.should_replace_codepoint(0x20AC))
        self.assertFalse(builder.should_replace_codepoint(0xAC00))
        self.assertFalse(builder.should_replace_codepoint(0x1100))
        self.assertFalse(builder.should_replace_codepoint(0x4E00))
        self.assertFalse(builder.should_replace_codepoint(0xF900))
        self.assertFalse(builder.should_replace_codepoint(0x2460))
        self.assertFalse(builder.should_replace_codepoint(0x24EA))
        self.assertFalse(builder.should_replace_codepoint(0x2780))
        self.assertFalse(builder.should_replace_codepoint(0x1F130))
        self.assertFalse(builder.should_replace_codepoint(0x20DD))
        self.assertFalse(builder.should_replace_codepoint(0xE000))

    def test_cjk_context_symbols_are_preserved_as_pretendard_glyphs(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        preserved = {
            0x20DD: "combining enclosing circle",
            0x2460: "circled digit one",
            0x24B6: "circled Latin capital A",
            0x2780: "dingbat circled sans-serif digit one",
            0x1F130: "squared Latin capital A",
            0xE13E: "private-use glyph",
        }
        for codepoint, label in preserved.items():
            with self.subTest(label=label):
                self.assertTrue(builder.should_keep_pretendard_codepoint(codepoint))

    def test_regular_italic_uses_inter_filename_without_regular_prefix(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        regular = {spec.style: spec for spec in builder.WEIGHT_SPECS}["Regular"]
        self.assertEqual(regular.inter_upright_stem, "Inter-Regular")
        self.assertEqual(regular.inter_italic_stem, "Inter-Italic")
        bold = {spec.style: spec for spec in builder.WEIGHT_SPECS}["Bold"]
        self.assertEqual(bold.inter_italic_stem, "Inter-BoldItalic")

    def test_revised_model_imports_inter_non_cjk_for_upright_and_italic(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        self.assertTrue(builder.should_import_inter_glyphs(italic=False))
        self.assertTrue(builder.should_import_inter_glyphs(italic=True))

    def test_inter_import_transform_converts_source_upm_to_base_upm(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")
        transform = builder.AffineTransform(
            scale_x=0.954055,
            scale_y=0.972168,
            translate_y=0.125,
        )

        self.assertAlmostEqual(
            builder.source_to_target_upm_scale(source_upm=2816, target_upm=2048),
            2048 / 2816,
        )
        self.assertEqual(
            builder.transformed_width(
                2084,
                transform,
                source_upm=2816,
                target_upm=2048,
                preserve_spacing=False,
            ),
            round(2084 * (2048 / 2816) * 0.954055),
        )
        self.assertEqual(
            builder.transformed_width(
                2084,
                transform,
                source_upm=2816,
                target_upm=2048,
                preserve_spacing=True,
                original_width=1446,
            ),
            1446,
        )
        self.assertEqual(
            builder.glyph_transform_matrix(
                transform,
                source_upm=2816,
                target_upm=2048,
            ),
            (
                0.954055 * (2048 / 2816),
                0,
                0,
                0.972168 * (2048 / 2816),
                0,
                0.125 * 2048,
            ),
        )
        self.assertEqual(builder.integer_fontforge_metric(12.4), 12)
        self.assertEqual(builder.integer_fontforge_metric(12.5), 12)
        self.assertEqual(builder.integer_fontforge_metric(12.6), 13)

    def test_inter_import_can_be_quiet_for_fontforge_anchor_warnings(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        self.assertIn(
            "with suppress_c_stderr(quiet):\n"
            "                imported = import_non_cjk_glyphs",
            pathlib.Path(builder.__file__).read_text(),
        )

    def test_explicit_build_can_discover_nested_inter_sources(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            font_path = root / "extras" / "otf" / "Inter-Italic.otf"
            font_path.parent.mkdir(parents=True)
            font_path.write_bytes(b"font")

            self.assertEqual(
                builder.resolve_font_source(None, root, "Inter-Italic"),
                font_path,
            )
            self.assertEqual(
                builder.resolve_font_source("custom.otf", root, "Inter-Italic"),
                pathlib.Path("custom.otf"),
            )


class MakefileContractTests(unittest.TestCase):
    def test_mapping_is_diagnostic_for_inter_import_model(self):
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn("--allow-large-residuals", makefile)

    def test_build_normalizes_otf_metadata_after_fontforge_generation(self):
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn("scripts/fix_metadata.py", makefile)
        self.assertIn("--pretendard-dir", makefile)

    def test_build_guards_italic_glyphs_against_upright_cjk(self):
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn("scripts/add_italic_cjk_guard.py", makefile)
        self.assertIn("GUARD_CLEARANCE ?= 30", makefile)
        # The guard reads the final metrics, so it has to run after FontForge
        # generation and after metadata normalization.
        self.assertLess(
            makefile.index("scripts/fix_metadata.py"),
            makefile.index("scripts/add_italic_cjk_guard.py"),
        )

    def test_prototype_uses_font_discovery_for_nested_source_layouts(self):
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn('--inter-dir "$(SOURCE_DIR)/inter"', makefile)
        self.assertNotIn("$(SOURCE_DIR)/inter/Inter-Regular.ttf", makefile)


class ItalicCjkGuardContractTests(unittest.TestCase):
    def test_geometry_buckets_round_toward_more_clearance(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        self.assertEqual(guard.round_up(42, 5), 45)
        self.assertEqual(guard.round_up(-3, 5), 0)
        self.assertEqual(guard.round_down(22, 5), 20)
        self.assertEqual(guard.round_down(-3, 5), -5)

    def test_pairs_that_already_clear_keep_their_designed_spacing(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        self.assertEqual(guard.guard_units(overhang=-15, side_bearing=73), 0)
        self.assertEqual(guard.guard_units(overhang=43, side_bearing=73), 0)

    def test_colliding_pairs_get_a_bucket_rounded_guard(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        # Forward, 'f가': 61 unit overhang against a 41 unit side bearing.
        self.assertEqual(guard.guard_units(overhang=65, side_bearing=40), 55)
        # Reverse, '다f': 80 unit overhang against an 11 unit side bearing.
        self.assertEqual(guard.guard_units(overhang=80, side_bearing=10), 100)

    def test_guard_keeps_clearance_for_every_member_of_a_bucket(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")
        clearance = 30
        bucket = 5

        for real_overhang in (61.0, 63.4, 64.9):
            for real_side_bearing in (41.0, 43.0, 44.9):
                units = guard.guard_units(
                    overhang=guard.round_up(real_overhang, bucket),
                    side_bearing=guard.round_down(real_side_bearing, bucket),
                    clearance=clearance,
                    bucket_size=bucket,
                )
                gap = real_side_bearing - real_overhang + units
                self.assertGreaterEqual(gap, clearance)

    def test_marks_and_zero_advance_glyphs_are_left_alone(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        # Inter contributes hundreds of zero-advance combining marks. Kerning
        # them would push the next glyph away by the mark's bounding box.
        self.assertFalse(guard.participates_in_spacing({0x0301}, 0))
        self.assertFalse(guard.participates_in_spacing({0x0308}, 0))
        self.assertFalse(guard.participates_in_spacing({0x20DC}, 0))
        self.assertTrue(guard.participates_in_spacing({ord("f")}, 354))
        self.assertTrue(guard.participates_in_spacing({ord("다")}, 864))

    def test_guard_sides_follow_the_source_split_and_skip_private_use(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        self.assertIs(guard.guard_side({ord("다")}), True)
        self.assertIs(guard.guard_side({ord("한")}), True)
        self.assertIs(guard.guard_side({0x3042}), True)
        self.assertIs(guard.guard_side({0x2460}), True)
        self.assertIs(guard.guard_side({ord("f")}), False)
        self.assertIs(guard.guard_side({ord("7")}), False)
        # Pretendard keeps private-use glyphs for its own composition
        # machinery; they are not CJK text and their advances do not describe
        # spacing, so they take no part in the guard.
        self.assertIsNone(guard.guard_side({0xE105}))
        self.assertIsNone(guard.guard_side({0xF8FF}))
        # Ambiguous glyphs reachable from both sides are left alone.
        self.assertIsNone(guard.guard_side({ord("f"), ord("다")}))

    def test_guard_ignores_marks_like_the_upstream_kern_lookups(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        # Pretendard and Inter both ship kern lookups with IgnoreMarks set. The
        # guard matches them so a combining mark between a letter and a CJK
        # glyph cannot hide the pair from the lookup.
        self.assertEqual(guard.IGNORE_MARKS_FLAG, 0x08)

    def test_guard_absorbs_the_kerning_the_sources_already_apply(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        # Lookups in one feature accumulate, so upstream kerning eats into the
        # guard. Pretendard and Inter kern tens of thousands of cross-script
        # pairs, often negatively, and the guard has to make that back.
        self.assertEqual(
            guard.guard_units(overhang=125, side_bearing=5, existing_adjustment=0),
            150,
        )
        self.assertEqual(
            guard.guard_units(overhang=125, side_bearing=5, existing_adjustment=-61),
            215,
        )
        # Upstream kerning that already opens the pair needs less from us.
        self.assertEqual(
            guard.guard_units(overhang=125, side_bearing=5, existing_adjustment=60),
            90,
        )
        self.assertEqual(
            guard.guard_units(overhang=65, side_bearing=40, existing_adjustment=100),
            0,
        )

    def test_pair_value_records_are_read_as_gap_changes(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")
        record = types.SimpleNamespace

        self.assertEqual(guard.gap_delta(record(XAdvance=-40), None), -40)
        # Displacing the first glyph right closes the gap; displacing the second
        # one right opens it. The second glyph's advance belongs to the next pair.
        self.assertEqual(guard.gap_delta(record(XPlacement=15), None), -15)
        self.assertEqual(guard.gap_delta(None, record(XPlacement=15)), 15)
        self.assertEqual(guard.gap_delta(None, record(XAdvance=99)), 0)
        self.assertEqual(guard.gap_delta(None, None), 0)

    def test_each_class_cell_is_sized_for_its_least_favourable_member(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        adjustments = {("f", "ga"): -20, ("f", "na"): -61, ("j", "ga"): 40}
        worst = guard.worst_adjustment_per_cell(
            adjustments,
            {"f": 65, "j": 65},
            {"ga": 40, "na": 40},
            {(65, 40): 4},
        )
        # Both f pairs and both j pairs land in the one cell, so it must assume
        # the -61 rather than averaging it away.
        self.assertEqual(worst[(65, 40)], -61)

    def test_a_cell_with_an_unkerned_member_cannot_assume_upstream_help(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        # Only one of the cell's four pairs is kerned, and positively. The other
        # three get nothing from upstream, so the cell must plan for zero.
        worst = guard.worst_adjustment_per_cell(
            {("f", "ga"): 40}, {"f": 65, "j": 65}, {"ga": 40, "na": 40}, {(65, 40): 4}
        )
        self.assertEqual(worst[(65, 40)], 0)

        # When every pair in the cell is kerned by the same positive amount,
        # that help is real and the guard can count on it.
        worst = guard.worst_adjustment_per_cell(
            {("f", "ga"): 40}, {"f": 65}, {"ga": 40}, {(65, 40): 1}
        )
        self.assertEqual(worst[(65, 40)], 40)

    def test_a_previous_guard_is_recognized_so_reruns_do_not_stack(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        def font_with(lookups, kern_indices):
            return {
                "GPOS": types.SimpleNamespace(
                    table=types.SimpleNamespace(
                        LookupList=types.SimpleNamespace(Lookup=lookups),
                        FeatureList=types.SimpleNamespace(
                            FeatureRecord=[
                                types.SimpleNamespace(
                                    FeatureTag="kern",
                                    Feature=types.SimpleNamespace(
                                        LookupListIndex=kern_indices
                                    ),
                                )
                            ]
                        ),
                    )
                )
            }

        classes = types.SimpleNamespace(Format=2)
        ours = types.SimpleNamespace(
            LookupType=2, LookupFlag=guard.IGNORE_MARKS_FLAG, SubTable=[classes, classes]
        )
        upstream = types.SimpleNamespace(LookupType=2, LookupFlag=0, SubTable=[classes])

        self.assertEqual(guard.find_existing_guard(font_with([upstream, ours], [0, 1])), 1)
        # Not ours: unflagged, not last in the kern feature, or not in it at all.
        self.assertIsNone(guard.find_existing_guard(font_with([upstream, upstream], [0, 1])))
        self.assertIsNone(guard.find_existing_guard(font_with([upstream, ours], [1, 0])))
        self.assertIsNone(guard.find_existing_guard(font_with([ours, upstream], [0])))

    def test_defaults_match_the_documented_build_settings(self):
        guard = load_module("add_italic_cjk_guard", "scripts/add_italic_cjk_guard.py")

        self.assertEqual(guard.DEFAULT_CLEARANCE, 30)
        self.assertEqual(guard.DEFAULT_BUCKET_SIZE, 5)


class FixMetadataContractTests(unittest.TestCase):
    def test_font_internal_versions_stay_aligned(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        self.assertEqual(builder.VERSION, "0.6.1")
        self.assertEqual(fixer.VERSION, "0.6.1")

    def test_head_revision_reports_our_version_not_pretendards(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        # FontForge leaves Pretendard's 1.309 in the generated head table, so
        # this has to be written explicitly or the font reports the wrong
        # version to anything that reads head rather than the name records.
        self.assertEqual(fixer.font_revision("0.2.0"), 0.2)
        self.assertEqual(fixer.font_revision("0.2.1"), 0.201)
        self.assertEqual(fixer.font_revision("1.0"), 1.0)
        self.assertEqual(fixer.font_revision(), fixer.font_revision(fixer.VERSION))
        # Refuse encodings that would collide with another release.
        for ambiguous in ("0.10.0", "0.2.100", "0"):
            with self.assertRaises(ValueError):
                fixer.font_revision(ambiguous)

    def test_cff_version_replaces_the_upstream_cid_version(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")
        top_dict = types.SimpleNamespace(CIDFontVersion=1.309)
        font = {
            "CFF ": types.SimpleNamespace(
                cff=types.SimpleNamespace(topDictIndex=[top_dict])
            )
        }

        fixer.normalize_cff_version(font)

        self.assertEqual(top_dict.version, "0.6.1")
        self.assertEqual(top_dict.CIDFontVersion, 0.601)

    def test_metadata_allows_installable_embedding_under_the_ofl(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")
        os2_table = types.SimpleNamespace(
            usWeightClass=400,
            usWidthClass=5,
            achVendID="TEST",
            fsType=8,
            fsSelection=0,
        )
        font = {"OS/2": os2_table}
        metadata = fixer.metadata_for_filename("SNUAppendard-Regular.otf", {})

        fixer.normalize_style_tables(font, metadata)

        self.assertEqual(os2_table.fsType, 0)

    def test_regular_italic_metadata_uses_family_style_and_postscript_names(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        metadata = fixer.metadata_for_filename(
            "SNUAppendard-RegularItalic.otf",
            {"PRETENDARD_TAG": "v1.3.9", "INTER_TAG": "v3.19"},
            "20260509T000000Z",
        )

        self.assertEqual(metadata.style, "Regular")
        self.assertTrue(metadata.italic)
        self.assertEqual(metadata.names[1], "SNU Appendard")
        self.assertEqual(metadata.names[2], "Italic")
        self.assertEqual(metadata.names[4], "SNU Appendard Italic")
        self.assertEqual(metadata.names[5], "Version 0.6.1")
        self.assertEqual(metadata.names[6], "SNUAppendard-RegularItalic")
        self.assertEqual(metadata.names[16], "SNU Appendard")
        self.assertEqual(metadata.names[17], "Italic")

    def test_metadata_preserves_upstream_rfn_and_license(self):
        builder = load_module("build_appendard", "scripts/build_appendard.py")
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        metadata = fixer.metadata_for_filename(
            "SNUAppendard-Regular.otf",
            {},
            "20260509T000000Z",
        )

        self.assertEqual(builder.COPYRIGHT_TEXT, fixer.COPYRIGHT_TEXT)
        self.assertIn("with Reserved Font Name Pretendard.", metadata.names[0])
        self.assertIn("The Inter Project Authors", metadata.names[0])
        self.assertIn("Hyeshik Chang (modifications)", metadata.names[0])
        self.assertIn("Reserved Font Name Pretendard", metadata.names[13])
        self.assertEqual(metadata.names[14], "https://openfontlicense.org")
        for name_id in (1, 4, 6, 16, 18):
            self.assertNotIn("Pretendard", metadata.names[name_id])

    def test_weighted_italic_metadata_preserves_weight_in_style_names(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        metadata = fixer.metadata_for_filename(
            "SNUAppendard-ExtraLightItalic.otf",
            {},
            "20260509T000000Z",
        )

        self.assertEqual(metadata.style, "ExtraLight")
        self.assertTrue(metadata.italic)
        self.assertEqual(metadata.weight_class, 200)
        self.assertEqual(metadata.names[2], "ExtraLight Italic")
        self.assertEqual(metadata.names[4], "SNU Appendard ExtraLight Italic")
        self.assertEqual(metadata.names[6], "SNUAppendard-ExtraLightItalic")
        self.assertEqual(metadata.names[17], "ExtraLight Italic")

    def test_metadata_uses_personal_not_institutional_attribution(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        metadata = fixer.metadata_for_filename(
            "SNUAppendard-Regular.otf",
            {},
            "20260509T000000Z",
        )
        joined_names = "\n".join(metadata.names.values())
        institutional_name = "Seoul " + "National University"

        self.assertNotIn(institutional_name, joined_names)
        self.assertIn("Hyeshik Chang", metadata.names[0])
        self.assertEqual(metadata.names[8], "Hyeshik Chang")
        self.assertEqual(metadata.names[9], "Hyeshik Chang")
        self.assertEqual(fixer.VENDOR_ID, "HCHK")

    def test_style_bits_are_computed_for_os2_and_head_tables(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        self.assertEqual(fixer.fs_selection(400, False), 0x40)
        self.assertEqual(fixer.fs_selection(400, True), 0x01)
        self.assertEqual(fixer.fs_selection(700, False), 0x20)
        self.assertEqual(fixer.fs_selection(700, True), 0x21)
        self.assertEqual(fixer.mac_style(400, False), 0x00)
        self.assertEqual(fixer.mac_style(400, True), 0x02)
        self.assertEqual(fixer.mac_style(700, True), 0x03)

    def test_vertical_metrics_scale_from_pretendard_upm_to_appendard_upm(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        self.assertEqual(fixer.scale_metric(1950, source_upm=2048, target_upm=1000), 952)
        self.assertEqual(fixer.scale_metric(-494, source_upm=2048, target_upm=1000), -241)
        self.assertEqual(fixer.scale_metric(1949, source_upm=2048, target_upm=1000), 952)
        self.assertEqual(fixer.scale_metric(494, source_upm=2048, target_upm=1000), 241)

    def test_font_wide_design_metrics_scale_from_pretendard_upm(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        scaled = fixer.scale_design_metrics(
            {
                "subscript_x_size": 1330,
                "subscript_y_size": 1230,
                "subscript_y_offset": 155,
                "superscript_y_offset": 715,
                "strikeout_size": 139,
                "strikeout_position": 652,
                "x_height": 1086,
                "cap_height": 1448,
                "post_underline_position": -258,
                "post_underline_thickness": 139,
                "cff_underline_position": -327,
                "cff_underline_thickness": 139,
                "absent_cff_metric": None,
            },
            source_upm=2048,
            target_upm=1000,
        )

        self.assertEqual(scaled["subscript_x_size"], 649)
        self.assertEqual(scaled["subscript_y_size"], 601)
        self.assertEqual(scaled["subscript_y_offset"], 76)
        self.assertEqual(scaled["superscript_y_offset"], 349)
        self.assertEqual(scaled["strikeout_size"], 68)
        self.assertEqual(scaled["strikeout_position"], 318)
        self.assertEqual(scaled["x_height"], 530)
        self.assertEqual(scaled["cap_height"], 707)
        self.assertEqual(scaled["post_underline_position"], -126)
        self.assertEqual(scaled["post_underline_thickness"], 68)
        self.assertEqual(scaled["cff_underline_position"], -160)
        self.assertEqual(scaled["cff_underline_thickness"], 68)
        self.assertIsNone(scaled["absent_cff_metric"])


class AnalyzeMappingContractTests(unittest.TestCase):
    def test_compute_transform_from_normalized_metrics(self):
        analyzer = load_module("analyze_mapping", "scripts/analyze_mapping.py")

        pretendard = analyzer.FontMeasurements(
            upm=2048,
            cap_height=0.75,
            x_height=0.5,
            glyphs={
                "H": analyzer.GlyphMeasurements(
                    bounds=(0.0, 0.1, 0.6, 0.75),
                    advance=0.7,
                    lsb=0.05,
                )
            },
        )
        inter = analyzer.FontMeasurements(
            upm=2048,
            cap_height=0.5,
            x_height=0.4,
            glyphs={
                "H": analyzer.GlyphMeasurements(
                    bounds=(0.0, 0.0, 0.35, 0.5),
                    advance=0.35,
                    lsb=0.025,
                )
            },
        )

        transform = analyzer.compute_transform(pretendard, inter)

        self.assertAlmostEqual(transform.scale_x, 2.0)
        self.assertAlmostEqual(transform.scale_y, 1.5)
        self.assertAlmostEqual(transform.translate_y, 0.1)

    def test_residuals_are_reported_in_reference_units(self):
        analyzer = load_module("analyze_mapping", "scripts/analyze_mapping.py")
        transform = analyzer.AffineTransform(scale_x=1.0, scale_y=1.0, translate_y=0.0)
        pretendard = analyzer.GlyphMeasurements(
            bounds=(0.0, 0.0, 10.0 / 2048.0, 10.0 / 2048.0),
            advance=20.0 / 2048.0,
            lsb=0.0,
        )
        inter = analyzer.GlyphMeasurements(
            bounds=(0.0, 0.0, 6.0 / 2048.0, 10.0 / 2048.0),
            advance=20.0 / 2048.0,
            lsb=0.0,
        )

        self.assertEqual(
            analyzer.glyph_residual_units(pretendard, inter, transform, 2048),
            4,
        )

    def test_large_residuals_are_reported_by_weight(self):
        analyzer = load_module("analyze_mapping", "scripts/analyze_mapping.py")
        report = {
            "weights": {
                "Regular": {"residuals_units": {"H": 5, "o": 3}},
                "Bold": {"residuals_units": {"H": 4, "o": 9}},
            }
        }

        self.assertEqual(
            analyzer.oversized_residuals(report, tolerance_units=4),
            {"Bold": {"o": 9}, "Regular": {"H": 5}},
        )


class PackageDistContractTests(unittest.TestCase):
    def test_license_headers_preserve_pretendard_rfn(self):
        project_license = (ROOT / "LICENSE").read_text()
        upstream_license = (ROOT / "licenses" / "Pretendard.txt").read_text()
        project_header = project_license.split("This Font Software", 1)[0]
        upstream_header = upstream_license.split("This Font Software", 1)[0]

        self.assertIn("with Reserved Font Name Pretendard.", project_header)
        self.assertIn("with Reserved Font Name Pretendard.", upstream_header)
        self.assertIn("Hyeshik Chang (modifications)", project_header)

    def test_find_otfs_requires_complete_eighteen_font_family(self):
        packager = load_module(
            "package_distribution", "scripts/package_distribution.py"
        )

        with tempfile.TemporaryDirectory() as tmp:
            otf_dir = pathlib.Path(tmp)
            for name in packager.EXPECTED_OTF_FILENAMES[:-1]:
                (otf_dir / name).write_bytes(b"font")

            with self.assertRaises(FileNotFoundError):
                packager.find_expected_otfs(otf_dir)

            (otf_dir / packager.EXPECTED_OTF_FILENAMES[-1]).write_bytes(b"font")
            self.assertEqual(
                [path.name for path in packager.find_expected_otfs(otf_dir)],
                list(packager.EXPECTED_OTF_FILENAMES),
            )

    def test_distribution_contains_only_flat_fonts_and_licenses(self):
        packager = load_module(
            "package_distribution_zip", "scripts/package_distribution.py"
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = pathlib.Path(tmp)
            otf_dir = project_root / "otf"
            otf_dir.mkdir()
            for name in packager.EXPECTED_OTF_FILENAMES:
                (otf_dir / name).write_bytes(b"font")
            for source, _ in packager.LICENSE_ENTRIES:
                path = project_root / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("license")

            output = project_root / "distribution.zip"
            packager.write_distribution(otf_dir, output, project_root)

            with ZipFile(output) as archive:
                self.assertEqual(
                    archive.namelist(), packager.expected_archive_entries()
                )
            self.assertIn(
                "SNUAppendard-RegularItalic.otf",
                packager.expected_archive_entries(),
            )
            self.assertNotIn(
                "SNUAppendard-Italic.otf", packager.expected_archive_entries()
            )
            self.assertTrue(
                all("/" not in name for name in packager.expected_archive_entries())
            )


class PackageReleaseContractTests(unittest.TestCase):
    def test_release_asset_names_match_github_release_convention(self):
        release = load_module("package_release", "scripts/package_release.py")

        self.assertEqual(release.release_zip_name("0.6.1"), "SNUAppendard-0.6.1.zip")
        # A tag-style "v0.6.1" names the same asset as a bare "0.6.1".
        self.assertEqual(release.release_zip_name("v0.6.1"), "SNUAppendard-0.6.1.zip")
        self.assertEqual(
            release.checksum_name("0.6.1"),
            "SNUAppendard-0.6.1.zip.sha256",
        )
        self.assertEqual(
            release.release_note_name("0.6.1"),
            "SNUAppendard-0.6.1-release-notes.md",
        )

    def test_release_zip_layout_matches_previous_github_asset(self):
        release = load_module("package_release", "scripts/package_release.py")
        packager = load_module(
            "package_distribution", "scripts/package_distribution.py"
        )

        self.assertEqual(
            release.expected_release_entries(),
            packager.expected_archive_entries(),
        )


class DownloadScriptContractTests(unittest.TestCase):
    def test_download_script_cleanup_trap_is_safe_with_nounset(self):
        script = (ROOT / "scripts/download_sources.sh").read_text()

        self.assertIn("TMP_DOWNLOAD_DIR", script)
        self.assertNotIn("trap 'rm -rf \"$tmp_dir\"' EXIT", script)

    def test_download_script_uses_versions_lock_unless_update_requested(self):
        script = (ROOT / "scripts/download_sources.sh").read_text()

        self.assertIn("lock_value", script)
        self.assertIn("UPDATE_SOURCES", script)


class SpecimenScriptContractTests(unittest.TestCase):
    def test_specimen_ignores_system_fonts_for_reproducible_comparisons(self):
        script = (ROOT / "scripts/make_specimen.sh").read_text()

        self.assertIn("--ignore-system-fonts", script)
        self.assertIn("--font-path \"$TMP_FONT_DIR\"", script)

    def test_specimen_tempdir_falls_back_when_default_tmp_is_restricted(self):
        script = (ROOT / "scripts/make_specimen.sh").read_text()

        self.assertIn("make_tmp_font_dir", script)
        self.assertIn("snu-appendard-fonts.XXXXXX", script)
        self.assertIn("mktemp -d /tmp/snu-appendard-fonts.XXXXXX", script)


if __name__ == "__main__":
    unittest.main()
