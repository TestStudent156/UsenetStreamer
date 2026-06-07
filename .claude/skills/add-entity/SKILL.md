---
name: add-entity
description: Scaffold a new HA sensor or binary_sensor entity, updating all required files in lockstep to pass hassfest validation.
disable-model-invocation: true
---

# add-entity

Adds a new entity to the integration. Expects args in the form:
`/add-entity <platform> <key> <label>`

- `platform`: `sensor` or `binary_sensor`
- `key`: snake_case identifier (e.g. `download_speed`)
- `label`: human-readable label for translations (e.g. `Download Speed`)

## Steps

1. **Add an EntityDescription** to the matching tuple in `custom_components/usenetstreamer/sensor.py` or `binary_sensor.py`.
   - Copy the structure of an existing description in that tuple.
   - Set `key=<key>`, `translation_key=<key>`.
   - Leave `value_fn` with a TODO comment — the caller must supply the correct data path from the admin API `values` dict.
   - For sensors: also set `native_unit_of_measurement`, `device_class`, and `state_class` if known.
   - For binary sensors: also set `device_class` if known.

2. **Update `custom_components/usenetstreamer/strings.json`**:
   - Under `entity.<platform>.<key>`, add `"name": "<label>"`.

3. **Update `custom_components/usenetstreamer/translations/en.json`**:
   - Mirror the same entry under `entity.<platform>.<key>.name`.

4. **Update `custom_components/usenetstreamer/translations/de.json`**:
   - Add the same entry, leaving the German translation identical to English for now and noting it needs translation.

5. **Confirm consistency**: verify `translation_key` in the description matches the key added in all three JSON files.

6. **Remind the user** to:
   - Fill in the correct `value_fn` pointing to the right field in `data["values"]`
   - Add a German translation in `de.json`
   - Run `/ha-compliance` to validate before pushing
