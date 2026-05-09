#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${SOURCE_DIR:-$ROOT_DIR/sources}"
ARCHIVE_DIR="${ARCHIVE_DIR:-$SOURCE_DIR/_archives}"
PRETENDARD_REPO="${PRETENDARD_REPO:-orioncactus/pretendard}"
INTER_REPO="${INTER_REPO:-rsms/inter}"
TMP_DOWNLOAD_DIR=""

lock_value() {
    local key="$1"
    local lock_file="$ROOT_DIR/versions.lock"

    if [ ! -f "$lock_file" ] || [ "${UPDATE_SOURCES:-0}" = "1" ]; then
        return 0
    fi

    awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$lock_file"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$1" >&2
        exit 1
    fi
}

release_json() {
    local repo="$1"
    local tag="$2"
    local url

    if [ -n "$tag" ]; then
        url="https://api.github.com/repos/$repo/releases/tags/$tag"
    else
        url="https://api.github.com/repos/$repo/releases/latest"
    fi

    wget -qO- "$url"
}

pick_asset_url() {
    local json_file="$1"
    local include_regex="$2"
    local exclude_regex="$3"

    jq -r \
        --arg include "$include_regex" \
        --arg exclude "$exclude_regex" \
        '.assets[]
         | select(.name | test($include))
         | select((.name | test($exclude)) | not)
         | .browser_download_url' \
        "$json_file" | head -n 1
}

download_asset() {
    local url="$1"
    local output="$2"

    if [ -f "$output" ]; then
        printf 'Using cached %s\n' "$output"
        return
    fi

    printf 'Downloading %s\n' "$url"
    wget -qO "$output" "$url"
}

extract_zip() {
    local zip_path="$1"
    local output_dir="$2"

    rm -rf "$output_dir"
    mkdir -p "$output_dir"
    unzip -q "$zip_path" -d "$output_dir"
}

write_lock() {
    local pretendard_tag="$1"
    local pretendard_url="$2"
    local inter_tag="$3"
    local inter_url="$4"

    cat > "$ROOT_DIR/versions.lock" <<EOF
PRETENDARD_REPO=$PRETENDARD_REPO
PRETENDARD_TAG=$pretendard_tag
PRETENDARD_ASSET_URL=$pretendard_url
INTER_REPO=$INTER_REPO
INTER_TAG=$inter_tag
INTER_ASSET_URL=$inter_url
FETCHED_AT=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
EOF
}

main() {
    require_command wget
    require_command jq
    require_command unzip

    mkdir -p "$ARCHIVE_DIR"

    TMP_DOWNLOAD_DIR="$(mktemp -d)"
    trap 'rm -rf "${TMP_DOWNLOAD_DIR:-}"' EXIT

    local pretendard_json="$TMP_DOWNLOAD_DIR/pretendard.json"
    local inter_json="$TMP_DOWNLOAD_DIR/inter.json"

    local requested_pretendard_tag
    local requested_inter_tag
    requested_pretendard_tag="${PRETENDARD_TAG:-$(lock_value PRETENDARD_TAG)}"
    requested_inter_tag="${INTER_TAG:-$(lock_value INTER_TAG)}"

    release_json "$PRETENDARD_REPO" "$requested_pretendard_tag" > "$pretendard_json"
    release_json "$INTER_REPO" "$requested_inter_tag" > "$inter_json"

    local resolved_pretendard_tag
    local resolved_inter_tag
    resolved_pretendard_tag="$(jq -r '.tag_name' "$pretendard_json")"
    resolved_inter_tag="$(jq -r '.tag_name' "$inter_json")"

    local pretendard_url
    local inter_url
    pretendard_url="$(pick_asset_url "$pretendard_json" '^Pretendard(-|_).*[.]zip$' '(GOV|Gov|gov|JP|Std)')"
    inter_url="$(pick_asset_url "$inter_json" '^Inter[-_].*[.]zip$' 'web|desktop')"

    if [ -z "$pretendard_url" ] || [ "$pretendard_url" = "null" ]; then
        printf 'Could not find a Pretendard release ZIP in %s %s\n' "$PRETENDARD_REPO" "$resolved_pretendard_tag" >&2
        exit 1
    fi
    if [ -z "$inter_url" ] || [ "$inter_url" = "null" ]; then
        printf 'Could not find an Inter release ZIP in %s %s\n' "$INTER_REPO" "$resolved_inter_tag" >&2
        exit 1
    fi

    local pretendard_zip="$ARCHIVE_DIR/pretendard-$resolved_pretendard_tag.zip"
    local inter_zip="$ARCHIVE_DIR/inter-$resolved_inter_tag.zip"

    download_asset "$pretendard_url" "$pretendard_zip"
    download_asset "$inter_url" "$inter_zip"

    extract_zip "$pretendard_zip" "$SOURCE_DIR/pretendard"
    extract_zip "$inter_zip" "$SOURCE_DIR/inter"
    write_lock "$resolved_pretendard_tag" "$pretendard_url" "$resolved_inter_tag" "$inter_url"

    printf 'Pretendard %s extracted to %s\n' "$resolved_pretendard_tag" "$SOURCE_DIR/pretendard"
    printf 'Inter %s extracted to %s\n' "$resolved_inter_tag" "$SOURCE_DIR/inter"
    printf 'Wrote %s\n' "$ROOT_DIR/versions.lock"
}

main "$@"
