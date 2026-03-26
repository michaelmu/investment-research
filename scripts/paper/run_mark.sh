#!/usr/bin/env bash
set -euo pipefail

DATE_ARG=${1:-""}
if [[ -n "$DATE_ARG" ]]; then
  DATE_FLAG=(--date "$DATE_ARG")
else
  DATE_FLAG=()
fi

# Ensure local imports work
export PYTHONPATH="$(pwd)/scripts/paper"

./scripts/paper/mark.py "${DATE_FLAG[@]}"
