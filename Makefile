PYTHON ?= python3
FONTFORGE ?= fontforge
TYPST ?= typst
VERSION ?= 0.1.0
BUILD_DIR ?= build
SOURCE_DIR ?= sources
DIST_DIR ?= dist
OTF_DIR ?= $(DIST_DIR)/otf
MAPPING_REPORT ?= $(BUILD_DIR)/mapping_report.json
PACKAGE_ZIP ?= $(DIST_DIR)/SNUAppendard-v$(VERSION).zip

.PHONY: sources mapping build prototype specimen dist test clean distclean

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
		--output-italic "$(BUILD_DIR)/SNUAppendard-Italic.otf"
	$(PYTHON) scripts/fix_metadata.py \
		--font "$(BUILD_DIR)/SNUAppendard-Regular.otf" \
		--font "$(BUILD_DIR)/SNUAppendard-Italic.otf" \
		--pretendard-dir "$(SOURCE_DIR)/pretendard" \
		--versions-lock versions.lock

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

specimen: build
	scripts/make_specimen.sh

dist: specimen
	$(PYTHON) scripts/package_dist.py \
		--input-dir "$(OTF_DIR)" \
		--output "$(PACKAGE_ZIP)" \
		--version "$(VERSION)" \
		--include specimen/specimen.pdf \
		--include README.md \
		--include LICENSE \
		--include NOTICE
	test -f "$(PACKAGE_ZIP)"

test:
	$(PYTHON) -m unittest discover -s tests

clean:
	rm -rf "$(BUILD_DIR)" "$(DIST_DIR)" specimen/specimen.pdf

distclean: clean
	rm -rf "$(SOURCE_DIR)"
