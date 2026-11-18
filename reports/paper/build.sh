#!/usr/bin/env bash
# Rebuild processed tables, figures, and the IEEE paper PDF from committed data.
# Usage (from anywhere): reports/paper/build.sh
# Needs: python3 with matplotlib + numpy, pdflatex + latexmk, IEEEtran (texlive).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
python3 scripts/process_results.py
python3 reports/paper/make_figures.py
cd reports/paper
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
latexmk -c >/dev/null
echo "built $(pwd)/paper.pdf ($(pdfinfo paper.pdf | awk '/^Pages/ {print $2}') pages)"
