#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${DIR}/run-all-evals.py" "$@"
