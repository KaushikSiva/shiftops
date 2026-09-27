#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo 'Usage: scripts/deploy.sh user@vultr-vm-or-ssh-alias' >&2
  exit 2
fi
target="$1"
if [[ ! "$target" =~ ^[a-zA-Z0-9_.@:-]+$ ]] || [[ "$target" == -* ]]; then
  echo 'Invalid SSH target' >&2; exit 2
fi
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
ssh "$target" 'docker compose version && mkdir -p ~/shiftops'
tar --exclude=.git --exclude=.venv --exclude=node_modules --exclude=web/dist --exclude=data --exclude=.env --exclude=artifacts --exclude=__pycache__ --exclude=.pytest_cache -czf - . | ssh "$target" 'tar -xzf - -C ~/shiftops'
ssh "$target" 'cd ~/shiftops && docker compose up -d --build && docker compose ps'
echo 'Set SITE_ADDRESS and SHIFTOPS_DEPLOYMENT=vultr in ~/shiftops/.env on the VM, then rerun docker compose up -d.'
echo 'Run scripts/public-smoke.py against the public URL to verify persisted end-to-end operation.'
