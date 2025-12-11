#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-help}

stop_services(){
  for svc in wpa_supplicant NetworkManager; do
    if systemctl is-active --quiet "$svc"; then
      echo "Stopping $svc"; sudo systemctl stop "$svc" || true
    fi
  done
}

start_services(){
  for svc in wpa_supplicant NetworkManager; do
    if systemctl is-enabled --quiet "$svc"; then
      echo "Starting $svc"; sudo systemctl start "$svc" || true
    fi
  done
}

case "$ACTION" in
  stop) stop_services;;
  start) start_services;;
  *) echo "Usage: $0 {stop|start}"; exit 1;;
esac


