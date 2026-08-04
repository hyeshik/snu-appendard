#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_OTF_DIR="${DIST_OTF_DIR:-$ROOT_DIR/dist/otf}"
PRETENDARD_DIR="${PRETENDARD_DIR:-$ROOT_DIR/sources/pretendard}"
SPECIMEN_SOURCE="${SPECIMEN_SOURCE:-$ROOT_DIR/specimen/specimen.typ}"
SPECIMEN_OUTPUT="${SPECIMEN_OUTPUT:-$ROOT_DIR/specimen/specimen.pdf}"

if ! command -v typst >/dev/null 2>&1; then
    printf 'Missing required command: typst\n' >&2
    exit 1
fi

if [ ! -d "$DIST_OTF_DIR" ]; then
    printf 'Missing built font directory: %s\n' "$DIST_OTF_DIR" >&2
    exit 1
fi

make_tmp_font_dir() {
    local tmp_parent="${TMPDIR:-/tmp}"

    mktemp -d "${tmp_parent%/}/snu-appendard-fonts.XXXXXX" 2>/dev/null ||
        mktemp -d /tmp/snu-appendard-fonts.XXXXXX
}

TMP_FONT_DIR="$(make_tmp_font_dir)"
trap 'rm -rf "$TMP_FONT_DIR"' EXIT

find "$DIST_OTF_DIR" -name '*.otf' -type f -exec cp {} "$TMP_FONT_DIR/" \;
if [ -d "$PRETENDARD_DIR" ]; then
    find "$PRETENDARD_DIR" -name '*.otf' -type f -exec cp {} "$TMP_FONT_DIR/" \;
fi

mkdir -p "$(dirname "$SPECIMEN_OUTPUT")"
typst compile \
    --ignore-system-fonts \
    --font-path "$TMP_FONT_DIR" \
    --input build_date="$(date -u '+%Y-%m-%d')" \
    "$SPECIMEN_SOURCE" \
    "$SPECIMEN_OUTPUT"

printf 'Wrote %s\n' "$SPECIMEN_OUTPUT"
