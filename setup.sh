#!/usr/bin/env bash
# Install project dependencies
set -e

if [ ! -f requirements.txt ]; then
  echo "requirements.txt not found" >&2
  exit 1
fi

python3 -m pip install -r requirements.txt

