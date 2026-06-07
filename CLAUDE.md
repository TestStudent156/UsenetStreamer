# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant **custom integration** (HACS-distributed) that monitors and remotely configures a
[UsenetStreamer](https://github.com/Sanket9225/UsenetStreamer) instance through its admin API. All
integration code lives under `custom_components/usenetstreamer/`. It is `local_polling` /
`integration_type: service` — there is no cloud component and no live download/stream telemetry
available from the upstream API, so entities cover availability, version, and configuration only.

## Commands

```bash
pip install -r requirements_test.txt   # test deps (pytest-homeassistant-custom-component, aioresponses)
pytest -v                              # run the full suite
pytest tests/test_coordinator.py -v    # single file
pytest tests/test_api.py::test_name    # single test
```

CI (`.github/workflows/validate.yml`) runs three independent jobs on Python 3.13: **hassfest**
(HA manifest validation), **hacs/action** (HACS repo validation, with `description,topics,brands`
ignored), and **pytest**. Match these locally before pushing — hassfest is strict about
`manifest.json` shape and `strings.json` ↔ `services.yaml` consistency.

## Architecture

Standard HA config-entry integration with a single device and a thin API client. Data flows
one direction for monitoring (poll) and the reverse for the one write path (service call):

- **`api.py`** — `UsenetStreamerClient`, the only thing that talks HTTP. GET/POST to
  `/admin/api/config`, auth via the `X-Addon-Token` header. Translates transport/HTTP failures into
  exactly two domain exceptions: `InvalidAuth` (401/403) and `CannotConnect` (timeouts, client
  errors, any `status >= 400`). Everything upstream catches these two, never raw aiohttp.
- **`coordinator.py`** — `UsenetStreamerCoordinator` (a `DataUpdateCoordinator`) polls
  `async_get_data` on the configured interval and re-raises client errors as `UpdateFailed`. Also
  exposes `async_set_config` for the write path (not part of the poll cycle).
- **`__init__.py`** — `async_setup_entry` builds the client + coordinator, does the first refresh,
  stores the coordinator on `entry.runtime_data` (typed via `UsenetStreamerConfigEntry =
  ConfigEntry[UsenetStreamerCoordinator]`), and forwards to the `BINARY_SENSOR` and `SENSOR`
  platforms. Also registers the **`apply_config`** service once (domain-level, shared across
  entries; removed only when the last entry unloads).
- **`entity.py`** — `UsenetStreamerEntity` base: `CoordinatorEntity` with `_attr_has_entity_name`
  and shared `DeviceInfo` keyed on `(DOMAIN, entry_id)` so every entity attaches to one device.
- **`sensor.py` / `binary_sensor.py`** — entities are declared as frozen `*EntityDescription`
  dataclasses carrying a `value_fn`. To add an entity, append a description to the `SENSORS` /
  `BINARY_SENSORS` tuple — no new class needed. `unique_id` is always `f"{entry_id}_{key}"`.
- **`config_flow.py`** — user step validates credentials via `client.async_validate()` and dedupes
  on host+port; options flow edits only `scan_interval` (min 5s, stored in `entry.options`).

### Key conventions

- **Admin API response shape:** monitoring values are nested under a `values` dict
  (`data["values"]["INDEXER_MANAGER_INDEXERS"]`), with a few top-level fields like `addonVersion`.
  All access goes through `.get("values", {}).get(...)` to tolerate missing keys. Booleans arrive as
  strings — use `_truthy()` in `binary_sensor.py`, don't compare to `True`.
- **Config keys** are centralized in `const.py` (`CONF_*`, `DEFAULT_*`, `ATTR_*`). Add new keys
  there, never inline string literals.
- **User-facing strings** live in `strings.json` and are mirrored into `translations/en.json` (+
  `de.json`). `translation_key` on each entity description points into these files. Adding an entity
  or a config/service field means updating these in lockstep, or hassfest fails.
- **The `apply_config` service** writes config back through the admin API. Its schema lives in
  `__init__.py` (`SERVICE_SCHEMA_APPLY_CONFIG`) and its UI/selector definition in `services.yaml`;
  keep both aligned. It resolves the target by `entry_id` and rejects entries whose domain isn't
  `usenetstreamer`.

## Testing notes

- `asyncio_mode = auto` (pytest.ini) — async tests need no `@pytest.mark.asyncio`.
- The `hass` fixture and `enable_custom_integrations` come from
  `pytest-homeassistant-custom-component` (auto-enabled in `conftest.py`).
- `conftest.py` monkey-patches `threading.enumerate` to hide a harmless pycares daemon thread that
  trips the harness's leftover-thread assertion on the pinned HA version. Don't remove it.
- Coordinator/client tests mock with `AsyncMock`; HTTP-level tests use `aioresponses`.
