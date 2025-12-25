#!/bin/bash -e
# ==============================================================================
# MoMo Stage - Prerun Script
# ==============================================================================
# This script runs before the stage and copies rootfs from previous stage.
# Required for custom stages in pi-gen.
# ==============================================================================

if [ ! -d "${ROOTFS_DIR}" ]; then
    # Copy rootfs from previous stage (stage1)
    PREV_STAGE_DIR="${WORK_DIR}/stage1"
    
    if [ -d "${PREV_STAGE_DIR}/rootfs" ]; then
        echo "[stage-momo] Copying rootfs from stage1..."
        mkdir -p "${ROOTFS_DIR}"
        rsync -aHAXx --exclude var/cache/apt/archives "${PREV_STAGE_DIR}/rootfs/" "${ROOTFS_DIR}/"
    else
        echo "[stage-momo] ERROR: No previous stage rootfs found!"
        echo "[stage-momo] Looking for: ${PREV_STAGE_DIR}/rootfs"
        exit 1
    fi
fi

echo "[stage-momo] Rootfs ready at ${ROOTFS_DIR}"

