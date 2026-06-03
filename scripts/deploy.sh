#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/b8vipvip/koko.git}"
APP_DIR="${APP_DIR:-/opt/koko}"
SERVICE_NAME="${SERVICE_NAME:-koko}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BRANCH="${BRANCH:-main}"

log() { printf '\033[1;32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy][WARN]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[deploy][ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ ! -d "$APP_DIR/.git" ]]; then
  log "Cloning $REPO_URL into $APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  log "Updating existing checkout in $APP_DIR"
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"
mkdir -p logs

if [[ ! -d .venv ]]; then
  log "Creating Python virtualenv"
  "$PYTHON_BIN" -m venv .venv
fi

log "Installing Python dependencies"
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  warn ".env does not exist. Copy .env.example to .env and fill DB/CORS/service settings before starting."
  warn "Command: cp $APP_DIR/.env.example $APP_DIR/.env && editor $APP_DIR/.env"
fi

if [[ -d migrations ]]; then
  warn "Database migrations were NOT executed automatically. Review and run manually after backup:"
  find migrations -maxdepth 1 -type f -name '*.sql' -print | sort
fi

if command -v systemctl >/dev/null 2>&1; then
  log "Reloading systemd and restarting $SERVICE_NAME"
  systemctl daemon-reload || true
  systemctl restart "$SERVICE_NAME" || warn "systemctl restart failed; install deploy/koko.service first or inspect journalctl."
  sleep 2
  systemctl --no-pager --full status "$SERVICE_NAME" || warn "Service status check returned non-zero."
else
  warn "systemctl not available; start manually with: .venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 --chdir server app:app"
fi

log "Deployment finished"
