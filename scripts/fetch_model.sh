#!/usr/bin/env bash
# Download one GGUF from a pinned Hugging Face revision into models/ and verify its SHA-256.
# Usage: scripts/fetch_model.sh <repo> <revision> <filename> <expected-sha256>
set -euo pipefail
(($# == 4)) || { sed -n '2,3p' "$0"; exit 2; }
repo=$1 rev=$2 file=$3 want=$4
dest=models/$file
[[ -e $dest ]] && { echo "exists: $dest" >&2; exit 1; }
mkdir -p models
curl -fL --retry 3 -C - -o "$dest.part" "https://huggingface.co/$repo/resolve/$rev/$file"
got=$(sha256sum "$dest.part" | cut -d' ' -f1)
[[ $got == "$want" ]] || { echo "sha256 mismatch for $file: got $got want $want (kept $dest.part)" >&2; exit 1; }
mv "$dest.part" "$dest"
echo "ok $dest $got $(stat -c %s "$dest") bytes"
