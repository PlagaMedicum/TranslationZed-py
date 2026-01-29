#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  exit 0
fi

sudo apt-get update
sudo apt-get install -y \
  libegl1 \
  libgl1 \
  libxkbcommon-x11-0
