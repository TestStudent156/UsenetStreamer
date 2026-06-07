#!/usr/bin/env sh
# Translate Home Assistant add-on options (/data/options.json) into the
# environment variables UsenetStreamer reads, then hand off to the app.
set -e

OPTIONS=/data/options.json

get() {
  jq -r --arg k "$1" '.[$k] // empty' "$OPTIONS"
}

# Required: the app returns HTTP 503 on guarded routes until this is set.
export ADDON_SHARED_SECRET="$(get shared_secret)"

# Optional extras — only export when the user actually set them.
STREAM_TOKEN="$(get stream_token)"
[ -n "$STREAM_TOKEN" ] && export ADDON_STREAM_TOKEN="$STREAM_TOKEN"

BASE_URL="$(get base_url)"
[ -n "$BASE_URL" ] && export ADDON_BASE_URL="$BASE_URL"

# Persist runtime config (runtime-env.json) on the add-on's /data volume.
export CONFIG_DIR=/data/config
mkdir -p "$CONFIG_DIR"

cd /usr/src/app
echo "[usenetstreamer] starting on port 7000 (config dir: ${CONFIG_DIR})"
exec npm start
