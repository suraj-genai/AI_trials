#!/bin/bash
set -euo pipefail

SOURCE_DIR="/solution"
TARGET_DIR="/app"

FILES=(
    allocator.c
    allocator.h
    metadata.c
    metadata.h
)

for file in "${FILES[@]}"; do
    if [[ ! -f "${SOURCE_DIR}/${file}" ]]; then
        echo "ERROR: Missing reference file: ${file}" >&2
        ls -la "${SOURCE_DIR}" >&2
        exit 1
    fi

    install -m 0644 "${SOURCE_DIR}/${file}" "${TARGET_DIR}/${file}"
done

echo "Protocol 2 reference implementation installed."
