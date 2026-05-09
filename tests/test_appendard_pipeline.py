import importlib.util
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        self.assertEqual(builder.postscript_style_name("Regular", True), "Italic")
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

    def test_prototype_uses_font_discovery_for_nested_source_layouts(self):
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn('--inter-dir "$(SOURCE_DIR)/inter"', makefile)
        self.assertNotIn("$(SOURCE_DIR)/inter/Inter-Regular.ttf", makefile)


class FixMetadataContractTests(unittest.TestCase):
    def test_regular_italic_metadata_uses_family_style_and_postscript_names(self):
        fixer = load_module("fix_metadata", "scripts/fix_metadata.py")

        metadata = fixer.metadata_for_filename(
            "SNUAppendard-Italic.otf",
            {"PRETENDARD_TAG": "v1.3.9", "INTER_TAG": "v3.19"},
            "20260509T000000Z",
        )

        self.assertEqual(metadata.style, "Regular")
        self.assertTrue(metadata.italic)
        self.assertEqual(metadata.names[1], "SNU Appendard")
        self.assertEqual(metadata.names[2], "Italic")
        self.assertEqual(metadata.names[4], "SNU Appendard Italic")
        self.assertEqual(metadata.names[5], "Version 001.000; Pretendard v1.3.9; Inter v3.19; build 20260509T000000Z")
        self.assertEqual(metadata.names[6], "SNUAppendard-Italic")
        self.assertEqual(metadata.names[16], "SNU Appendard")
        self.assertEqual(metadata.names[17], "Italic")

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
    def test_find_otfs_requires_complete_eighteen_font_family(self):
        packager = load_module("package_dist", "scripts/package_dist.py")

        with tempfile.TemporaryDirectory() as tmp:
            otf_dir = pathlib.Path(tmp)
            for name in packager.EXPECTED_OTF_FILENAMES[:-1]:
                (otf_dir / name).write_bytes(b"font")

            with self.assertRaises(FileNotFoundError):
                packager.find_expected_otfs(otf_dir)

            (otf_dir / packager.EXPECTED_OTF_FILENAMES[-1]).write_bytes(b"font")
            self.assertEqual(
                [path.name for path in packager.find_expected_otfs(otf_dir)],
                packager.EXPECTED_OTF_FILENAMES,
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


if __name__ == "__main__":
    unittest.main()
