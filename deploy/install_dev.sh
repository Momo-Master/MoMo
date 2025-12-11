#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
pip3 install -e .[dev]
pre-commit install

echo "Dev environment ready."

