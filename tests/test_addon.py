"""Tests for UsenetStreamer add-on helpers (slug discovery, safe writes)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.usenetstreamer import addon
from custom_components.usenetstreamer.addon import (
    async_discover_addon_slug,
    async_ensure_addon_running,
    async_set_addon_options_safe,
    async_start_addon_safe,
)
from custom_components.usenetstreamer.const import (
    ADDON_SLUG_LEGACY,
    ADDON_SLUG_SUFFIX,
    OPTIONS_WRITE_BASE_BACKOFF,
    OPTIONS_WRITE_MAX_RETRIES,
)


def _info(state: AddonState, options: dict | None = None) -> AddonInfo:
    return AddonInfo(
        available=True,
        hostname="local-usenetstreamer",
        options=options or {},
        state=state,
        update_available=False,
        version="1.7.12" if state == AddonState.RUNNING else None,
    )


# ----- async_discover_addon_slug -------------------------------------------


async def test_discover_finds_suffix_match(hass: HomeAssistant) -> None:
    with patch.object(
        addon,
        "async_send_hassio_command",
        AsyncMock(
            return_value={
                "addons": [
                    {"slug": "core_samba"},
                    {"slug": "local_a1b2c3d4_usenetstreamer"},
                    {"slug": f"local{ADDON_SLUG_SUFFIX}"},
                ]
            }
        ),
    ):
        slug = await async_discover_addon_slug(hass)
    assert slug == "local_a1b2c3d4_usenetstreamer"


async def test_discover_falls_back_to_legacy_local_slug(hass: HomeAssistant) -> None:
    with patch.object(
        addon,
        "async_send_hassio_command",
        AsyncMock(
            return_value={"addons": [{"slug": ADDON_SLUG_LEGACY}]}
        ),
    ):
        slug = await async_discover_addon_slug(hass)
    assert slug == ADDON_SLUG_LEGACY


async def test_discover_returns_none_when_unreachable(
    hass: HomeAssistant,
) -> None:
    with patch.object(
        addon, "async_send_hassio_command", AsyncMock(side_effect=OSError)
    ):
        assert await async_discover_addon_slug(hass) is None


async def test_discover_returns_none_when_no_match(hass: HomeAssistant) -> None:
    with patch.object(
        addon,
        "async_send_hassio_command",
        AsyncMock(
            return_value={"addons": [{"slug": "core_mosquitto"}, {"slug": "other"}]}
        ),
    ):
        assert await async_discover_addon_slug(hass) is None


async def test_discover_handles_list_payload(hass: HomeAssistant) -> None:
    """Some Supervisor versions return a bare list from /addons."""
    with patch.object(
        addon,
        "async_send_hassio_command",
        AsyncMock(return_value=[{"slug": f"x{ADDON_SLUG_SUFFIX}"}]),
    ):
        assert await async_discover_addon_slug(hass) == f"x{ADDON_SLUG_SUFFIX}"


# ----- async_set_addon_options_safe ----------------------------------------


def _mgr_with_options(current_options: dict) -> MagicMock:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(
        return_value=_info(AddonState.RUNNING, options=current_options)
    )
    mgr.async_set_addon_options = AsyncMock()
    return mgr


async def test_safe_set_options_preserves_unspecified_keys(
    hass: HomeAssistant,
) -> None:
    mgr = _mgr_with_options(
        {"shared_secret": "OLD", "stream_token": "KEEP", "base_url": "https://x"}
    )
    merged = await async_set_addon_options_safe(
        mgr, {"shared_secret": "NEW"}
    )
    mgr.async_set_addon_options.assert_awaited_once_with(
        {
            "shared_secret": "NEW",
            "stream_token": "KEEP",
            "base_url": "https://x",
        }
    )
    assert merged["shared_secret"] == "NEW"
    assert merged["stream_token"] == "KEEP"


async def test_safe_set_options_retries_then_succeeds(
    hass: HomeAssistant,
) -> None:
    mgr = _mgr_with_options({"shared_secret": "OLD"})
    mgr.async_set_addon_options = AsyncMock(
        side_effect=[AddonError("transient"), None]
    )
    with patch("custom_components.usenetstreamer.addon.asyncio.sleep", AsyncMock()):
        await async_set_addon_options_safe(mgr, {"shared_secret": "NEW"})
    assert mgr.async_set_addon_options.await_count == 2


async def test_safe_set_options_raises_after_exhausting_retries(
    hass: HomeAssistant,
) -> None:
    mgr = _mgr_with_options({})
    mgr.async_set_addon_options = AsyncMock(side_effect=AddonError("boom"))
    with (
        patch("custom_components.usenetstreamer.addon.asyncio.sleep", AsyncMock()),
        pytest.raises(AddonError),
    ):
        await async_set_addon_options_safe(mgr, {"shared_secret": "X"})
    assert mgr.async_set_addon_options.await_count == OPTIONS_WRITE_MAX_RETRIES


# ----- async_start_addon_safe ----------------------------------------------


async def test_safe_start_succeeds_first_try(hass: HomeAssistant) -> None:
    mgr = MagicMock()
    mgr.async_start_addon = AsyncMock()
    await async_start_addon_safe(mgr)
    mgr.async_start_addon.assert_awaited_once()


async def test_safe_start_retries_then_raises(hass: HomeAssistant) -> None:
    mgr = MagicMock()
    mgr.async_start_addon = AsyncMock(side_effect=AddonError("nope"))
    with (
        patch("custom_components.usenetstreamer.addon.asyncio.sleep", AsyncMock()),
        pytest.raises(AddonError),
    ):
        await async_start_addon_safe(mgr)
    assert mgr.async_start_addon.await_count == OPTIONS_WRITE_MAX_RETRIES


# ----- async_ensure_addon_running -----------------------------------------


async def test_ensure_running_not_installed_raises_not_ready(
    hass: HomeAssistant,
) -> None:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(return_value=_info(AddonState.NOT_INSTALLED))
    with pytest.raises(ConfigEntryNotReady, match="not installed"):
        await async_ensure_addon_running(hass, "local_a1b2c3d4_usenetstreamer")
    mgr.async_schedule_start_addon.assert_not_called()


async def test_ensure_running_not_running_schedules_start(
    hass: HomeAssistant,
) -> None:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(return_value=_info(AddonState.NOT_RUNNING))
    mgr.async_schedule_start_addon = MagicMock()
    with pytest.raises(ConfigEntryNotReady, match="is starting"):
        await async_ensure_addon_running(hass, ADDON_SLUG_LEGACY)
    mgr.async_schedule_start_addon.assert_called_once()


async def test_ensure_running_running_returns_info(hass: HomeAssistant) -> None:
    info = _info(AddonState.RUNNING, options={"shared_secret": "S"})
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(return_value=info)
    result = await async_ensure_addon_running(hass, ADDON_SLUG_LEGACY)
    assert result is info


async def test_ensure_running_error_message_names_slug(
    hass: HomeAssistant,
) -> None:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(side_effect=AddonError("kaput"))
    with pytest.raises(ConfigEntryNotReady, match="local_a1b2c3d4_usenetstreamer"):
        await async_ensure_addon_running(hass, "local_a1b2c3d4_usenetstreamer")


# ----- get_addon_manager ---------------------------------------------------


def test_get_addon_manager_uses_passed_slug() -> None:
    """The manager is constructed with the slug we pass in."""
    fake_hass = MagicMock()
    mgr = addon.get_addon_manager(fake_hass, "local_xyz_usenetstreamer")
    # No memoization: different slugs produce different manager instances.
    mgr2 = addon.get_addon_manager(fake_hass, "local_other_usenetstreamer")
    assert mgr is not mgr2
    assert mgr is not None
