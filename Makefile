PYTHON ?= python3
FONTFORGE ?= fontforge
TYPST ?= typst
VERSION ?= $(shell sed -n 's/^VERSION = "\(.*\)"$$/\1/p' scripts/build_appendard.py)
BUILD_DIR ?= build
SOURCE_DIR ?= sources
DIST_DIR ?= dist
OTF_DIR ?= $(DIST_DIR)/otf
MAPPING_REPORT ?= $(BUILD_DIR)/mapping_report.json
GUARD_CLEARANCE ?= 30
PACKAGE_ZIP ?= $(DIST_DIR)/SNUAppendard-$(VERSION).zip

.PHONY: sources mapping build prototype specimen distribution release test clean distclean

sources:
	scripts/download_sources.sh

mapping:
	mkdir -p "$(BUILD_DIR)"
	$(PYTHON) scripts/analyze_mapping.py \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--inter-dir "$(SOURCE_DIR)/inter" \
		--output "$(MAPPING_REPORT)" \
		--allow-large-residuals

prototype: mapping
	mkdir -p "$(BUILD_DIR)"
	$(FONTFORGE) -lang=py -script scripts/build_appendard.py \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--inter-dir "$(SOURCE_DIR)/inter" \
		--transform "$(MAPPING_REPORT)" \
		--weight Regular \
		--output "$(BUILD_DIR)/SNUAppendard-Regular.otf" \
		--output-italic "$(BUILD_DIR)/SNUAppendard-RegularItalic.otf"
	$(PYTHON) scripts/fix_metadata.py \
		--font "$(BUILD_DIR)/SNUAppendard-Regular.otf" \
		--font "$(BUILD_DIR)/SNUAppendard-RegularItalic.otf" \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--versions-lock versions.lock
	$(PYTHON) scripts/add_italic_cjk_guard.py \
		--font "$(BUILD_DIR)/SNUAppendard-Regular.otf" \
		--font "$(BUILD_DIR)/SNUAppendard-RegularItalic.otf" \
		--clearance "$(GUARD_CLEARANCE)"

build: mapping
	rm -rf "$(OTF_DIR)"
	mkdir -p "$(OTF_DIR)"
	$(FONTFORGE) -lang=py -script scripts/build_appendard.py \
		--all \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--inter-dir "$(SOURCE_DIR)/inter" \
		--transform "$(MAPPING_REPORT)" \
		--output-dir "$(OTF_DIR)"
	$(PYTHON) scripts/fix_metadata.py \
		--input-dir "$(OTF_DIR)" \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--versions-lock versions.lock
	$(PYTHON) scripts/add_italic_cjk_guard.py \
		--input-dir "$(OTF_DIR)" \
		--clearance "$(GUARD_CLEARANCE)"

specimen: build
	scripts/make_specimen.sh

distribution: build
	$(PYTHON) scripts/package_distribution.py \
		--input-dir "$(OTF_DIR)" \
		--output "$(PACKAGE_ZIP)"
	test -f "$(PACKAGE_ZIP)"

release:
	$(PYTHON) scripts/package_release.py \
		--version "$(VERSION)" \
		--python "$(PYTHON)"

test:
	$(PYTHON) -m unittest discover -s tests

clean:
	rm -rf "$(BUILD_DIR)" "$(DIST_DIR)" specimen/specimen.pdf

distclean: clean
	rm -rf "$(SOURCE_DIR)"
