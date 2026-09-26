#!/usr/bin/env bash
set -euo pipefail

uv sync
(cd frontend && npm ci && npm run build)

if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "Created config.json from config.example.json; edit users and secret."
fi
