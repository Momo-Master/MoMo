#!/usr/bin/env bash
set -euo pipefail

# Simple pi-gen wrapper to build a preconfigured MoMo image for Pi 5
# Requires: docker or native pi-gen deps. This is a scaffold.

WORKDIR=${WORKDIR:-/tmp/momo-pigen}
STAGE_DIR=$(dirname "$0")/stage-momo

log() { echo "[image] $(date -u +%F_%T) $*"; }

main() {
  mkdir -p "$WORKDIR"
  cd "$WORKDIR"
  if [ ! -d pi-gen ]; then
    git clone --depth 1 https://github.com/RPi-Distro/pi-gen.git
  fi
  cp -r "$STAGE_DIR" pi-gen/stage-momo
  # Configure pi-gen for bookworm and pi5
  cat > pi-gen/config <<EOF
IMG_NAME=MoMo
RELEASE=bookworm
TARGET_HOSTNAME=momo
FIRST_USER_NAME=pi
FIRST_USER_PASS=raspberry
ENABLE_SSH=1
STAGE_LIST="stage0 stage1 stage2 stage-momo"
EOF
  log "Starting build ..."
  cd pi-gen
  ./build.sh
  log "Build finished. See deploy artifacts in pi-gen/deploy/"
}

main "$@"


