# UsenetStreamer for Home Assistant

Monitoring and remote configuration of a
[UsenetStreamer](https://github.com/Sanket9225/UsenetStreamer) instance via its
admin API.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/TestStudent156/hass-usenetstreamer` with category
   **Integration**.
3. Install **UsenetStreamer**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → **UsenetStreamer**.

## Configuration

| Field | Notes |
|------|------|
| Host | UsenetStreamer host/IP |
| Port | default `7000` |
| Use SSL | enable for https |
| Admin token | your `ADDON_SHARED_SECRET` |
| Verify SSL | disable for self-signed certs |

## Entities

Addon version, indexer manager, configured indexers, plus Easynews-enabled,
health-check-enabled, and reachable binary sensors.

> Note: UsenetStreamer exposes no live download/stream metrics, so monitoring
> is limited to availability, version, and configuration.

## Service: apply_config

Use `usenetstreamer.apply_config` to push config values to an existing
UsenetStreamer config entry.

Service data:

- `entry_id`: target integration entry ID
- `values`: key/value mapping sent to `/admin/api/config` as `{"values": ...}`
