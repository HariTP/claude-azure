#!/usr/bin/env bash
set -euo pipefail
sudo systemctl disable --now claude-azure-local.service
sudo rm -f /etc/systemd/system/claude-azure-local.service
sudo systemctl daemon-reload
PROFILE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/claude-azure-local"
if [[ -f "$PROFILE_DIR/installed.json" ]]; then
  rm -f "$HOME/.local/bin/claude-azure"
fi
if [[ ${1:-} == --purge ]]; then
  sudo rm -rf /etc/claude-azure-local
  sudo rm -f /etc/credstore.encrypted/claude-azure-local.key
  # rm removes symlinks here without following them into the shared chat store.
  rm -rf -- "$PROFILE_DIR"
fi
printf '%s\n' 'Gateway startup removed. Original Claude chat directories were not removed.'
