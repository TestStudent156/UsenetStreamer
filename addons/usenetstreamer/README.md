# UsenetStreamer add-on

Runs [UsenetStreamer](https://github.com/Sanket9225/UsenetStreamer) (a Usenet →
Stremio bridge) as a Home Assistant add-on. The companion
[UsenetStreamer integration](https://github.com/TestStudent156/hass-usenetstreamer)
installs, starts, and monitors this add-on for you — you normally don't add it by
hand.

It is a **thin wrapper** around the upstream image
`ghcr.io/sanket9225/usenetstreamer` (pinned to a release tag); a small `run.sh`
maps the add-on options below to the environment variables the app expects.

## Installation (local add-on, for development/verification)

1. Copy this `usenetstreamer/` folder into the host's `addons` share (e.g. via the
   Samba or Advanced SSH add-on) so it lives at `/addons/usenetstreamer/`.
2. Settings → Add-ons → Add-on Store → ⋮ → **Check for updates**. The add-on
   appears under **Local add-ons** as `local_usenetstreamer`.
3. Install it, set **Admin shared secret** in the Configuration tab, then Start.

## Options

| Option | Required | Description |
|--------|----------|-------------|
| `shared_secret` | yes | Admin token (`ADDON_SHARED_SECRET`). Protects the admin API/dashboard; the app returns HTTP 503 until it is set. |
| `stream_token` | no | Separate token gating the streaming endpoints (`ADDON_STREAM_TOKEN`). |
| `base_url` | no | Public HTTPS base URL for reverse-proxy / manifest URLs (`ADDON_BASE_URL`). |

All other UsenetStreamer settings (indexers, Easynews, NZBDav, TMDB/TVDB, sorting…)
are configured from the in-app admin dashboard at `http://<host>:7000/<shared_secret>/admin/`
or through the integration's `usenetstreamer.apply_config` service.

## Notes

- Architectures: `amd64`, `aarch64` (the upstream image ships no armv7 build).
- Persistent config is stored under `/data/config` (`runtime-env.json`).
- The app serves plain HTTP on port 7000; Stremio needs HTTPS, so put a reverse
  proxy in front for external streaming use.
- The container runs as the unprivileged `node` user (uid 1000) so the app's
  own writes (npm cache, `runtime-env.json`, etc.) work without root. `/data`
  is Supervisor-managed and may be root-owned; the entry script chowns the
  config subtree to `node:node` on start.

## Troubleshooting

**Add-on won't start / `run.sh` exits silently.** Check the Supervisor
add-on log. The wrapper now logs a one-line summary of the resolved
options at start (e.g. `[usenetstreamer] starting on port 7000 (config
dir: /data/config; secret: set; stream_token: empty; base_url: empty)`).
If `secret: empty` appears, set the **Admin shared secret** in the
Configuration tab and restart.

**"Could not validate the connection" / add-on_validation_failed.** The
add-on is up but the admin API is unreachable. Most common causes:
empty `shared_secret` (see above), the app still starting (wait a few
seconds and retry), or the add-on log shows an upstream crash. Read the
add-on log via **Settings → Add-ons → UsenetStreamer → Log**.

**Config flow says "add-on not found".** The Supervisor doesn't see the
add-on. If you installed via a Git repository, check the slug under
**Settings → Add-ons** — store-installed add-ons are slugged as
`local_<hash>_usenetstreamer` and the integration auto-discovers them.
