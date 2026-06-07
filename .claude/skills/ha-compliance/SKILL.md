---
name: ha-compliance
description: Check HA integration files for hassfest-style consistency issues before pushing. Catches manifest shape, strings/translations/services lockstep violations.
disable-model-invocation: true
---

# ha-compliance

Runs a hassfest-style consistency check across the integration files. Read each file and report violations — do NOT modify files, only report.

## Checks to perform

### 1. manifest.json shape
Read `custom_components/usenetstreamer/manifest.json` and verify ALL of these keys are present:
`domain`, `name`, `codeowners`, `config_flow`, `documentation`, `homeassistant`, `integration_type`, `iot_class`, `requirements`, `version`

Report any missing keys.

### 2. strings.json ↔ translations lockstep
Read `custom_components/usenetstreamer/strings.json`, `translations/en.json`, and `translations/de.json`.

For every `translation_key` that appears under the `entity` section in strings.json:
- Verify the same key path exists in `translations/en.json`
- Verify the same key path exists in `translations/de.json`

For every field under `services` in strings.json:
- Verify the matching key exists in `translations/en.json` and `translations/de.json`

Report any mismatches.

### 3. strings.json ↔ services.yaml lockstep
Read `custom_components/usenetstreamer/services.yaml` and `strings.json`.

For every service defined in services.yaml:
- Verify the service name has a matching entry under `services` in strings.json with at least `name` and `description`.

For every field listed under a service's `fields` in services.yaml:
- Verify the field has a matching entry under `services.<service>.fields` in strings.json.

Report any fields present in one but not the other.

### 4. SERVICE_SCHEMA_APPLY_CONFIG ↔ services.yaml field alignment
Read `custom_components/usenetstreamer/__init__.py` and extract the keys defined in `SERVICE_SCHEMA_APPLY_CONFIG`.
Read `custom_components/usenetstreamer/services.yaml` and extract the fields defined under `apply_config`.

Report any field that exists in the schema but not in services.yaml, or vice versa.

### 5. Booleans and raw API access
Scan `custom_components/usenetstreamer/binary_sensor.py` for any `== True` or `== False` comparisons. These should use `_truthy()` instead.

Scan `custom_components/usenetstreamer/coordinator.py` and `api.py` for any direct `data["values"]` access without `.get()`. These should use `.get("values", {}).get(...)`.

## Output format

Print a summary:
```
ha-compliance: <N> issue(s) found

[FAIL] manifest.json: missing key 'documentation'
[FAIL] strings.json: key entity.sensor.foo missing from translations/de.json
[OK]   services.yaml <-> strings.json: all fields aligned
...
```

Exit with a reminder to fix all FAIL items before pushing.
