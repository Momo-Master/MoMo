#!/bin/bash -e
# ==============================================================================
# MoMo Stage - Host Script (runs on build host)
# ==============================================================================
# This script runs on the host machine before chroot.
# Use for file copies that don't need chroot environment.
# ==============================================================================

# Copy MoMo source to rootfs
install -d "${ROOTFS_DIR}/opt/momo"

# We'll clone from GitHub in chroot instead of copying local
# This ensures we get a clean, complete copy

echo "[stage-momo] Host setup complete"

