# UsenetStreamer: HassOS "writing issues" — diagnosis & fix spec

**Date:** 2026-06-11
**Status:** Draft (interview-completed; awaiting implementation plan + sign-off).
**Parent spec:** `2026-06-07-usenetstreamer-addon-install-design.md`
(the Supervisor-only add-on install flow this integration depends on).

## Problem statement (user-reported)

> "It is not working on HassOS because of writing issues."

The user has confirmed via interview that the **integration cannot connect** to the
UsenetStreamer add-on, the failure is **silent (no useful data, no clear log)**,
the add-on itself **crashes / won't start**, and the **integration entities are
never created**. They are deploying the add-on via a **Git add-on repo
(`store.add_repository`)** — i.e. the *follow-up* distribution path that the
parent spec marked as out of scope. They want a **full diagnosis + fix + tests**
that touches **both the integration and the add-on**, including **dropping
privileges explicitly** in the add-on and **retry + clearer errors** in the
integration.

This spec is the bridge between the MVP (local add-on via Samba) and the
distribution path (Git repo → store install) that the user is actually
exercising. It targets the **real failure surface on a real HassOS host**, not
the synthetic one assumed by the parent spec.

## What the user is actually doing

Based on the interview:

- **Deployment path:** add-on is built from a GitHub repo added via
  `store.add_repository` (Supervisor hashes the repo URL and prefixes the slug,
  so the on-disk slug becomes `local_<hash>_usenetstreamer`, not
  `local_usenetstreamer`).
- **Symptom:** config flow appears to succeed-ish, no entity is ever created,
  no useful error in the add-on log, no useful error in the HA core log.
- **Where they are stuck:** they don't know the real slug, the add-on log is
  empty, and they can't tell whether the failure is in the add-on or the
  integration.

## Why the MVP design breaks on this path

The parent spec assumes a **local** add-on at `local_usenetstreamer` and a
**non-supervised user** that the add-on already happens to work for. Both
assumptions are wrong for the user's path:

1. **Slug mismatch.** The integration hardcodes
   `ADDON_SLUG = "local_usenetstreamer"` in `const.py`. On a store-installed
   add-on the slug is `local_<hash>_usenetstreamer`. Calls to
   `async_get_addon_info()` therefore raise `AddonError`, which:
   - in `addon.py::async_ensure_addon_running` becomes `ConfigEntryNotReady`
     (entity creation never runs) and
   - in `config_flow.py::_async_get_addon_info` becomes
     `AbortFlow("addon_info_failed")` (a *loud* abort — but the user is
     reporting a *silent* failure, so something else is masking it).
2. **Add-on crash / won't start.** The current `Dockerfile` runs as **root**
   (`FROM ghcr.io/sanket9225/usenetstreamer:1.7.12` with no `USER` directive;
   `apk add --no-cache jq` and `COPY run.sh` happen at build time, then the
   container's PID 1 is `run.sh` running as root). The upstream app
   (`node:22-alpine`) is built to run as the unprivileged `node` user, so any
   internal write it attempts (npm cache, runtime-env.json under
   `$CONFIG_DIR`, etc.) is either denied or produces an empty/garbled
   `runtime-env.json` — and the supervisor's add-on log only shows the
   container's stdout/stderr, which is silent if the app dies before logging
   or if the supervisor captures the wrong stream.
3. **Silent failure surface.** Three independent sinks can swallow errors:
   - `async_set_addon_options({...})` is fire-and-checked for the wrong
     shape: the parent spec calls it with
     `{CONF_SHARED_SECRET: self.shared_secret}`, but the add-on's `options:`
     block in `config.yaml` declares defaults for `shared_secret`,
     `stream_token`, and `base_url`. The Supervisor requires **all declared
     options to be present** when writing, so writing only `shared_secret`
     drops `stream_token` and `base_url` to the schema defaults — which is
     fine for those fields but means the integration's options are out of
     sync with what the user sees in the Supervisor UI.
   - `run.sh` has `set -e` and unconditionally exports
     `ADDON_SHARED_SECRET="$(get shared_secret)"`. If the user clears the
     field in the Supervisor UI, the export is an empty string and the app
     boots into its "returns 503" state, but the add-on itself does **not**
     crash — so the add-on log stays empty and the integration sees
     `CannotConnect` instead of a clear "shared secret is empty" error.
   - The config flow's `async_step_finish_addon_setup` does **not** validate
     the connection (`client.async_validate()` is imported but not called
     there). The entry is created regardless of whether the add-on is
     reachable, so the user sees a "successful" config flow followed by
     silent retry. This is the most likely source of the "silent" symptom.
4. **Entities never created.** When the add-on is unreachable, the
   `async_setup_entry` call path runs:
   `addon.async_ensure_addon_running` → `ConfigEntryNotReady` → HA retries
   the setup → no platforms are forwarded → no entities are ever registered.
   The HA frontend shows the entry as "Setting up" indefinitely. There is no
   log line on the *user* side, because `ConfigEntryNotReady` is a normal
   control-flow signal, not an error.

In short: **the integration's MVP assumes a local add-on and a permissive
container, and the user's actual environment is a store-installed add-on with
a rootless expectation. The interaction between those two mismatches is what
produces the "writing issues" symptom.**

## Goals

1. Make the integration work against a **store-installed** (`local_<hash>_…`)
   add-on with no manual user configuration of the slug.
2. Make the add-on **boot as a non-root user** so that the upstream app's
   writes to its working directory and `CONFIG_DIR` actually succeed on
   HassOS.
3. Make the **config flow validate the connection** before creating the
   entry, and surface a clear, localized error if it can't.
4. Make the **add-on options write** idempotent and round-trip-safe (writes
   the full options dict, not just the keys the integration knows about, so
   the user can also configure `stream_token` / `base_url` from the Supervisor
   UI without the integration clobbering them).
5. Add tests covering the new behaviors so the failure mode is reproducible
   in CI and so a regression is caught before it ships.

## Non-goals

- Publishing the add-on to a public add-on store (still the parent's
  follow-up).
- Adding HTTPS / ingress for the Stremio side (unrelated).
- Surfacing the upstream app's ~98 optional config keys as add-on options
  (still left to the in-app dashboard / `apply_config` service).
- Touching the write-side (`apply_config` service → POST
  `/admin/api/config`) — the existing path already works and the user's
  symptom is on the *read / setup* path, not the write-back path.

## Decisions

1. **Slug discovery at runtime, not hardcoded.** The integration stops
   hardcoding `ADDON_SLUG = "local_usenetstreamer"`. Instead, on the first
   config-flow step it asks Supervisor for the list of installed add-ons,
   filters to those whose `slug` ends with `_usenetstreamer` and whose
   `options` schema matches (has a `shared_secret` field), and pins that
   one. The discovered slug is stored on the config entry so subsequent
   setup calls don't re-discover. The hardcoded name remains as a
   *fallback* for the legacy case (and for tests that want a stable value).
2. **Add-on runs as the `node` user.** The `Dockerfile` gains
   `USER node` after the build steps, and `run.sh` is moved to a path owned
   by `node` (`/usr/local/bin/run.sh`) and `USER`'d. The `mkdir -p
   "$CONFIG_DIR"` in `run.sh` is changed to `chown` to the `node` user so
   the upstream app can write into `/data/config` even though `/data` is
   owned by `root` (Supervisor default).
3. **`run.sh` tolerates an empty / missing `shared_secret` without
   `set -e`-aborting.** It logs a clear warning and continues; the upstream
   app's documented "returns 503" behavior is then what the integration
   surfaces, not a crash.
4. **Config flow validates before creating the entry.**
   `async_step_finish_addon_setup` calls `client.async_validate()` and on
   `CannotConnect` / `InvalidAuth` returns a *form error* on the previous
   step (or a new `cannot_connect` / `invalid_auth` abort with a reason
   pointing to the add-on log) instead of creating a doomed entry.
5. **Options write is full and merge-safe.** `async_set_addon_options` is
   always called with the union of *existing* add-on options and the
   integration's `shared_secret`. This avoids the partial-write trap and
   also fixes the "user changed `stream_token` in Supervisor UI" case.
6. **Retry with backoff for transient write failures.** When
   `async_set_addon_options` or `async_start_addon` raises a recoverable
   `AddonError` (e.g., a timeout), the integration logs and retries up to N
   times with exponential backoff, then surfaces a clear error to the user
   if it still fails. The constants (`MAX_RETRIES`, base backoff) live in
   `const.py`.
7. **`/data` is assumed writable by the Supervisor-managed `node` user.**
   No `map:` block in `config.yaml` (the parent's choice stands); we
   instead ensure the `node` user can write into `/data/config` from inside
   the container via `chown` in `run.sh`.

## Changes — by file

### `addons/usenetstreamer/Dockerfile` (add-on side)

- Add `USER node` *after* `apk add` and `COPY run.sh` (build still runs as
  root, runtime does not).
- Move `run.sh` to `/usr/local/bin/run.sh` (or `/opt/run.sh`) and `chown
  node:node` it; `chmod 755`. The `node` user's home in the upstream image
  is `/home/node` and group is `node`.
- Drop `apk add --no-cache jq` only if a smaller alternative is acceptable;
  the design prefers keeping `jq` (cheap) and keeping the `run.sh` portable.

### `addons/usenetstreamer/run.sh` (add-on side)

- Replace `set -e` with `set -eu` and a guarded `trap` that logs the
  failing line.
- Make `ADDON_SHARED_SECRET` an **optional** export: if it's empty, log
  `[usenetstreamer] WARNING: shared_secret is empty; admin API will return
  503 until set` and continue (do not abort).
- Change `mkdir -p "$CONFIG_DIR"` to `mkdir -p "$CONFIG_DIR" && chown
  node:node "$CONFIG_DIR"` so the `node` user can write into it even when
  `/data` is owned by root.
- Add a one-line summary of the resolved options at startup
  (length-bounded, no secret logging): `[usenetstreamer] options: secret
  set=<yes/no> stream_token set=<yes/no> base_url=<value|empty>`.
- Keep `exec npm start` as the final line.

### `addons/usenetstreamer/config.yaml` (add-on side)

- No structural change. Optional: bump `version` to `0.2.0` to force a
  rebuild on devices that already have the add-on installed locally.
- Document in the add-on `README.md` (or `DOCS.md`) that the add-on runs
  as the `node` user and that `/data/config` is owned by `node`.

### `custom_components/usenetstreamer/const.py` (integration side)

- Add `CONF_DISCOVERED_SLUG = "discovered_slug"` (stored on entry.data so
  setup doesn't re-discover on every restart).
- Add retry constants: `OPTIONS_WRITE_MAX_RETRIES = 3`,
  `OPTIONS_WRITE_BASE_BACKOFF = 0.5` (seconds).
- Keep the existing `ADDON_SLUG` constant as `ADDON_SLUG_LEGACY = "local_usenetstreamer"`
  for the legacy / test path; add `ADDON_SLUG_SUFFIX = "_usenetstreamer"`
  for the discovery matcher.
- Add `REASON_NO_VALIDATION = "addon_validation_failed"` and friends (see
  the strings section below).

### `custom_components/usenetstreamer/addon.py` (integration side)

- Add `async_discover_addon_slug(hass) -> str | None` that calls the
  Supervisor add-on store API (or `async_get_addon_discovery_info`) to
  list installed add-ons and returns the first slug ending in
  `ADDON_SLUG_SUFFIX`. Falls back to `ADDON_SLUG_LEGACY` and to `None` if
  the Supervisor isn't reachable.
- Refactor `async_ensure_addon_running(hass, slug=None)` to accept a
  *slug argument* (or to look it up from the singleton if not given). The
  helper raises `ConfigEntryNotReady` with a *slug-aware* message that
  names the discovered slug, so HA's retry log is at least informative.
- Add a small `async_set_addon_options_safe(addon_manager, options)` that
  fetches the current `addon_info.options` and merges the new keys into
  it (full-options write), then calls `async_set_addon_options` with
  retries + backoff. Raises `AddonError` after exhausting retries.
- Add `async_start_addon_safe(addon_manager)` with the same retry
  behavior.

### `custom_components/usenetstreamer/config_flow.py` (integration side)

- In `async_step_user`, after `is_hassio()` and the unique-id checks,
  attempt slug discovery via the new helper. If discovery fails, abort
  with a new `addon_not_found` reason (with a hint: "is the UsenetStreamer
  add-on installed in the Supervisor store?").
- In `async_step_installation`, pass the discovered slug through every
  subsequent step (stashed on `self`).
- In `async_step_configure_addon`, call the new
  `async_set_addon_options_safe` instead of the raw
  `async_set_addon_options`. On exhaustion, surface a form error
  ("cannot_connect" or a new "addon_options_write_failed") with a link
  to the Supervisor add-on log.
- In `async_step_finish_addon_setup`, **call `client.async_validate()`**
  before creating the entry. Map `InvalidAuth` to a new `invalid_auth`
  abort reason; map `CannotConnect` to `cannot_connect` (already a
  standard HA reason) with a description that points to the add-on log.
- Update the abort reasons: add `addon_not_found`,
  `addon_validation_failed`, `invalid_auth`. Keep the existing
  `not_hassio`, `addon_info_failed`, `addon_install_failed`,
  `addon_start_failed`, `already_configured` (for back-compat with
  translations).

### `custom_components/usenetstreamer/__init__.py` (integration side)

- In `async_setup_entry`, when `CONF_USE_ADDON` is true, read the
  discovered slug from `entry.data[CONF_DISCOVERED_SLUG]` (falling back
  to legacy) and pass it to `async_ensure_addon_running`.
- Continue to surface `ConfigEntryNotReady` on transient failures so HA
  retries, but ensure the message names the discovered slug.

### `custom_components/usenetstreamer/strings.json` (and `translations/{en,de}.json`)

- Add the new abort reasons:
  - `addon_not_found` (en: "UsenetStreamer add-on not found. Install it
    from the Supervisor store first.")
  - `addon_validation_failed` (en: "Could not validate the connection to
    the UsenetStreamer add-on. Check the Supervisor add-on log.")
  - `invalid_auth` (en: "The UsenetStreamer add-on rejected the
    configured shared secret. Re-run the add-on configuration and make
    sure the values match.")
- Update `config.step.configure_addon` description to note that the
  integration will preserve the user's other options (`stream_token`,
  `base_url`).
- Update `config.abort.not_hassio` description to mention
  "Home Assistant OS / Supervised installations only".
- Mirror all of the above into `de.json` in lockstep (hassfest requires
  this).

### Tests

- `tests/test_addon.py` (new) — unit tests for
  `async_discover_addon_slug`, `async_set_addon_options_safe`,
  `async_start_addon_safe` (success, partial-failure, full-failure paths;
  retry-exhaustion path).
- `tests/test_config_flow.py` (extend) — new cases:
  - slug discovery returns `None` → abort `addon_not_found`;
  - slug discovery returns a hash-prefixed slug → flow uses it, entry
    stores `CONF_DISCOVERED_SLUG`;
  - `async_step_finish_addon_setup` calls `client.async_validate()` and
    aborts `invalid_auth` / `cannot_connect` on the relevant exceptions;
  - `async_set_addon_options_safe` merges with existing options (the
    user can keep a `stream_token` they set in the Supervisor UI).
- `tests/test_init.py` (extend) — `async_setup_entry` uses the
  discovered slug; `ConfigEntryNotReady` messages name the discovered
  slug.
- Keep existing `test_api.py`, `test_coordinator.py`, `test_sensor.py`,
  `test_services.py` unchanged (the API/coordinator/entities/services
  code is untouched).

### Documentation

- `addons/usenetstreamer/README.md` — add a **Troubleshooting → "Add-on
  won't start"** section that points users at the new `run.sh` warning
  lines (empty `shared_secret` → "WARNING: shared_secret is empty; admin
  API will return 503 until set") and the Supervisor add-on log path.
- `README.md` (repo root) — add a one-paragraph "Installing the
  add-on from a Git repo" note that links to the
  `store.add_repository` flow and explicitly notes the hash-prefixed
  slug pattern, so users know what to expect.
- `custom_components/usenetstreamer/README.md` (if present) — note that
  the integration auto-discovers the add-on slug, so no manual config
  is needed.

## Verification

### Local (CI-matching)

```bash
pip install -r requirements_test.txt
pytest -v
pytest tests/test_config_flow.py -v
pytest tests/test_init.py -v
pytest tests/test_addon.py -v
```

CI (`.github/workflows/validate.yml`) must continue to pass on Python
3.13: **hassfest** (manifest shape + strings/services lockstep),
**hacs/action**, **pytest**.

### Live (via ha-mcp, on the actual HassOS host)

1. Copy the updated add-on folder to the host's add-ons share (or push
   the new commit to the Git repo used by `store.add_repository`).
2. Settings → Add-ons → Add-on Store → ⋮ → **Check for updates** to
   pick up the `version: 0.2.0` bump.
3. `ha_get_addon slug=local_usenetstreamer` (or the actual hash slug)
   and confirm `state: started` and that the Configuration tab now
   shows the `shared_secret` persisted across the restart.
4. Re-run the integration's config flow; confirm the new
   `addon_not_found` / `invalid_auth` / `cannot_connect` aborts are
   reachable (smoke-test by temporarily breaking the token) and that
   the happy path now creates entities on the first try.
5. Pull the add-on log and confirm the new `[usenetstreamer] options:
   secret set=<yes/no> …` summary line is present and informative.
6. Confirm a clean uninstall of the integration uninstalls the add-on
   (the existing `integration_created_addon` flag still drives this).

## Out of scope (still)

- Publishing the add-on to the official add-on store.
- TLS / ingress.
- Surfacing the upstream app's full ~98-key config as add-on options.
- Any change to the `apply_config` write-back service (it works as
  designed and is unrelated to the user's symptom).

## Open questions

- Does the Supervisor expose a stable API to enumerate add-ons for
  `store.add_repository`-installed add-ons in the version on the
  target HassOS (2026.05.1)? If not, the discovery helper needs a
  fallback that uses the AddonManager's own `slug` argument and
  requires the user to confirm the slug in the config flow. (Will be
  resolved during implementation by reading Supervisor source /
  docs.)
- Should the integration warn on startup if `entry.data` was created
  with a discovered slug that is no longer installed? (Currently: no
  — degraded mode is to keep the entry and surface `CannotConnect`
  on every poll.)
- Should we add a service `usenetstreamer.refresh_addon_slug` for the
  case where the user uninstalls + reinstalls the add-on under a
  different hash? (Defer to follow-up unless trivial.)
