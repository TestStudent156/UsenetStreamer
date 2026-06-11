#!/usr/bin/env sh
# Translate Home Assistant add-on options (/data/options.json) into the
# environment variables UsenetStreamer reads, then hand off to the app.
#
# Designed to run as the unprivileged `node` user on HassOS. /data is
# Supervisor-managed and may be owned by root; we chown the bits we need
# so the app can write its runtime-env.json and any other config artifacts.
set -u
trap 'echo "[usenetstreamer] run.sh aborting on error at line $LINENO" >&2; exit 1' ERR

OPTIONS=/data/options.json

get() {
  jq -r --arg k "$1" '.[$k] // empty' "$OPTIONS"
}

# Ensure CONFIG_DIR exists and is writable by the current user (node on the
# shipped image). /data itself is Supervisor-managed; we only chown the
# config subtree to avoid touching anything we don't own.
CONFIG_DIR_VALUE="$(get CONFIG_DIR)"
if [ -z "$CONFIG_DIR_VALUE" ]; then
  CONFIG_DIR=/data/config
else
  CONFIG_DIR="$CONFIG_DIR_VALUE"
fi
mkdir -p "$CONFIG_DIR" 2>/dev/null || true
# Best-effort chown; ignore failures (e.g. when not running as root, which
# is the normal case after the Dockerfile's `USER node`).
chown -R node:node "$CONFIG_DIR" 2>/dev/null || true
export CONFIG_DIR

# Required: the app returns HTTP 503 on guarded routes until this is set.
# We tolerate an empty value (e.g. user cleared it in the Supervisor UI)
# and log a clear warning instead of aborting the add-on — the app stays
# up and the integration surfaces a useful error from the config flow.
SHARED_SECRET="$(get shared_secret)"
if [ -z "$SHARED_SECRET" ]; then
  echo "[usenetstreamer] WARNING: shared_secret is empty; admin API will return 503 until set in the Supervisor Configuration tab" >&2
fi
export ADDON_SHARED_SECRET="$SHARED_SECRET"

# Optional extras — only export when the user actually set them.
STREAM_TOKEN="$(get stream_token)"
if [ -n "$STREAM_TOKEN" ]; then
  export ADDON_STREAM_TOKEN="$STREAM_TOKEN"
fi

BASE_URL="$(get base_url)"
if [ -n "$BASE_URL" ]; then
  export ADDON_BASE_URL="$BASE_URL"
fi

# Non-secret summary of resolved options so the Supervisor add-on log tells
# the user (and the integration's "addon_validation_failed" error) what's
# actually configured.
if [ -n "$SHARED_SECRET" ]; then
  SECRET_STATUS="set"
else
  SECRET_STATUS="empty"
fi
if [ -n "$STREAM_TOKEN" ]; then
  STREAM_STATUS="set"
else
  STREAM_STATUS="empty"
fi
if [ -n "$BASE_URL" ]; then
  BASE_STATUS="$BASE_URL"
else
  BASE_STATUS="empty"
fi
echo "[usenetstreamer] starting on port 7000 (config dir: $CONFIG_DIR; secret: $SECRET_STATUS; stream_token: $STREAM_STATUS; base_url: $BASE_STATUS)"

cd /usr/src/app
exec npm start
