#!/usr/bin/env bash
# ==============================================================================
# MoMo Pi 5 Image Builder
# ==============================================================================
# Creates a ready-to-flash SD card image with MoMo pre-installed.
#
# Usage:
#   ./make_image.sh              # Build with defaults
#   ./make_image.sh --docker     # Build using Docker (recommended)
#   ./make_image.sh --clean      # Clean previous build
#
# Requirements:
#   - Linux host (Ubuntu/Debian recommended)
#   - Docker (for --docker mode) OR native pi-gen dependencies
#   - ~10GB free disk space
#   - 1-2 hours build time
#
# Output:
#   deploy/momo-pi5-YYYYMMDD.img.xz
# ==============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="${WORKDIR:-/tmp/momo-pigen}"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/../../releases}"
STAGE_DIR="$SCRIPT_DIR/stage-momo"

# Image settings
IMG_NAME="momo-pi5"
IMG_VERSION="${IMG_VERSION:-$(date +%Y%m%d)}"
RELEASE="bookworm"
TARGET_HOSTNAME="momo"
FIRST_USER_NAME="pi"
FIRST_USER_PASS="raspberry"
LOCALE="en_GB.UTF-8"
TIMEZONE="UTC"
KEYBOARD="us"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[momo-image]${NC} $(date -u +%F_%T) $*"; }
warn() { echo -e "${YELLOW}[momo-image]${NC} $(date -u +%F_%T) WARNING: $*"; }
error() { echo -e "${RED}[momo-image]${NC} $(date -u +%F_%T) ERROR: $*" >&2; }

usage() {
    cat <<EOF
MoMo Pi 5 Image Builder

Usage: $0 [OPTIONS]

Options:
    --docker      Build using Docker (recommended, no deps needed)
    --clean       Clean previous build artifacts
    --lite        Build lite image (no desktop, smaller)
    --full        Build full image with all extras
    --help        Show this help

Environment Variables:
    WORKDIR       Build directory (default: /tmp/momo-pigen)
    OUTPUT_DIR    Output directory for final image
    IMG_VERSION   Image version string (default: YYYYMMDD)

Examples:
    $0 --docker           # Build with Docker
    $0 --clean --docker   # Clean and rebuild
EOF
    exit 0
}

check_deps() {
    log "Checking dependencies..."
    
    if [[ "$USE_DOCKER" == "true" ]]; then
        if ! command -v docker &> /dev/null; then
            error "Docker not found. Install Docker or run without --docker flag."
            exit 1
        fi
        log "Docker found: $(docker --version)"
    else
        local missing=()
        for cmd in git quilt parted qemu-arm-static; do
            if ! command -v "$cmd" &> /dev/null; then
                missing+=("$cmd")
            fi
        done
        
        if [[ ${#missing[@]} -gt 0 ]]; then
            error "Missing dependencies: ${missing[*]}"
            echo "Install with: sudo apt install git quilt parted qemu-user-static"
            exit 1
        fi
    fi
}

clean_build() {
    log "Cleaning previous build..."
    rm -rf "$WORKDIR"
    log "Clean complete."
}

setup_pigen() {
    log "Setting up pi-gen..."
    
    mkdir -p "$WORKDIR"
    cd "$WORKDIR"
    
    if [[ ! -d pi-gen ]]; then
        log "Cloning pi-gen..."
        git clone --depth 1 https://github.com/RPi-Distro/pi-gen.git
    else
        log "Updating pi-gen..."
        cd pi-gen && git pull && cd ..
    fi
    
    # Copy MoMo stage
    log "Copying MoMo stage..."
    rm -rf pi-gen/stage-momo
    cp -r "$STAGE_DIR" pi-gen/stage-momo
    
    # Create config
    log "Creating pi-gen config..."
    cat > pi-gen/config <<EOF
# MoMo Pi 5 Image Configuration
# Generated: $(date -u +%F_%T)

IMG_NAME=$IMG_NAME
RELEASE=bookworm
DEPLOY_DIR=\${PWD}/deploy
TARGET_HOSTNAME=$TARGET_HOSTNAME
FIRST_USER_NAME=$FIRST_USER_NAME
FIRST_USER_PASS=$FIRST_USER_PASS
ENABLE_SSH=1
LOCALE_DEFAULT=$LOCALE
TIMEZONE_DEFAULT=$TIMEZONE
KEYBOARD_KEYMAP=$KEYBOARD

# Build lite image (no desktop)
STAGE_LIST="stage0 stage1 stage2 stage-momo"

# Skip stages we don't need
SKIP_IMAGES=0

# Compression
DEPLOY_COMPRESSION=xz
COMPRESSION_LEVEL=6

# Use Raspberry Pi archive
APT_PROXY=""
EOF

    # Skip touch files from failed runs
    rm -f pi-gen/stage*/SKIP 2>/dev/null || true
    rm -rf pi-gen/work 2>/dev/null || true
    
    log "pi-gen setup complete."
}

build_native() {
    log "Starting native build..."
    cd "$WORKDIR/pi-gen"
    
    # Run build
    sudo ./build.sh
    
    log "Native build complete."
}

build_docker() {
    log "Starting Docker build..."
    cd "$WORKDIR/pi-gen"
    
    # Run Docker build
    ./build-docker.sh
    
    log "Docker build complete."
}

copy_output() {
    log "Copying output image..."
    
    mkdir -p "$OUTPUT_DIR"
    
    local src_img
    src_img=$(find "$WORKDIR/pi-gen/deploy" -name "*.img.xz" -type f | head -1)
    
    if [[ -z "$src_img" ]]; then
        error "No image found in deploy directory!"
        exit 1
    fi
    
    local dest_img="$OUTPUT_DIR/${IMG_NAME}-${IMG_VERSION}.img.xz"
    cp "$src_img" "$dest_img"
    
    # Generate checksums
    log "Generating checksums..."
    cd "$OUTPUT_DIR"
    sha256sum "$(basename "$dest_img")" > "$(basename "$dest_img").sha256"
    
    log "Image created: $dest_img"
    log "SHA256: $(cat "$(basename "$dest_img").sha256")"
    
    # Show size
    local size
    size=$(du -h "$dest_img" | cut -f1)
    log "Image size: $size"
}

main() {
    local USE_DOCKER=false
    local DO_CLEAN=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --docker)
                USE_DOCKER=true
                shift
                ;;
            --clean)
                DO_CLEAN=true
                shift
                ;;
            --lite)
                # Already lite by default
                shift
                ;;
            --full)
                warn "Full image not yet supported, building lite."
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                error "Unknown option: $1"
                usage
                ;;
        esac
    done
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            🔥 MoMo Pi 5 Image Builder                        ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Version: $IMG_VERSION                                          ║"
    echo "║  Output:  $OUTPUT_DIR                          ║"
    echo "║  Docker:  $USE_DOCKER                                           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Clean if requested
    if [[ "$DO_CLEAN" == "true" ]]; then
        clean_build
    fi
    
    # Check dependencies
    check_deps
    
    # Setup pi-gen
    setup_pigen
    
    # Build
    if [[ "$USE_DOCKER" == "true" ]]; then
        build_docker
    else
        build_native
    fi
    
    # Copy output
    copy_output
    
    echo ""
    log "🎉 Build complete!"
    echo ""
    echo "Flash with:"
    echo "  xzcat $OUTPUT_DIR/${IMG_NAME}-${IMG_VERSION}.img.xz | sudo dd of=/dev/sdX bs=4M status=progress"
    echo ""
}

main "$@"
