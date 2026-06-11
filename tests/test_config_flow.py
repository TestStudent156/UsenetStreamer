"""Tests for the UsenetStreamer config flow (add-on install flow)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.usenetstreamer.api import (
    CannotConnect,
    InvalidAuth,
    UsenetStreamerClient,
)
from custom_components.usenetstreamer.const import (
    ADDON_SLUG_LEGACY,
    CONF_ADMIN_TOKEN,
    CONF_DISCOVERED_SLUG,
    CONF_HOST,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_USE_ADDON,
    DOMAIN,
)

CF = "custom_components.usenetstreamer.config_flow"

# A non-legacy slug to exercise the discovery / store-installed path.
HASH_SLUG = "local_a1b2c3d4_usenetstreamer"


def _info(state: AddonState, hostname: str | None = None, options=None) -> AddonInfo:
    return AddonInfo(
        available=True,
        hostname=hostname,
        options=options or {},
        state=state,
        update_available=False,
        version="1.7.12" if state == AddonState.RUNNING else None,
    )


def _mock_manager(infos: list[AddonInfo]) -> MagicMock:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(side_effect=infos)
    mgr.async_install_addon = AsyncMock()
    mgr.async_set_addon_options = AsyncMock()
    mgr.async_start_addon = AsyncMock()
    mgr.async_stop_addon = AsyncMock()
    mgr.async_uninstall_addon = AsyncMock()
    return mgr


_PROGRESS = (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE)


async def _advance(hass: HomeAssistant, result: dict):
    """Drive show_progress steps until a terminal/form result."""
    for _ in range(12):
        if result["type"] not in _PROGRESS:
            return result
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    raise AssertionError("flow did not settle")


async def _init(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


# --- existing / preserved tests -------------------------------------------


async def test_aborts_without_supervisor(hass: HomeAssistant) -> None:
    with patch(f"{CF}.is_hassio", return_value=False):
        result = await _init(hass)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_hassio"


async def test_single_instance_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=HASH_SLUG)),
    ):
        result = await _init(hass)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_aborts_when_addon_not_found(hass: HomeAssistant) -> None:
    """No add-on installed → addon_not_found abort before any step."""
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=None)),
    ):
        result = await _init(hass)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_not_found"


async def test_install_flow_creates_entry(hass: HomeAssistant) -> None:
    mgr = _mock_manager(
        [
            _info(AddonState.NOT_INSTALLED),
            _info(
                AddonState.RUNNING,
                hostname=HASH_SLUG.replace("_", "-"),
                options={"shared_secret": "TESTSECRET"},
            ),
        ]
    )
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=HASH_SLUG)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
        patch(
            f"{CF}.async_set_addon_options_safe",
            AsyncMock(return_value={"shared_secret": "TESTSECRET"}),
        ),
        patch(
            f"{CF}.async_start_addon_safe",
            AsyncMock(),
        ),
        patch.object(UsenetStreamerClient, "async_validate", AsyncMock()),
        patch(
            "custom_components.usenetstreamer.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await _advance(hass, await _init(hass))
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "configure_addon"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"shared_secret": "TESTSECRET"}
        )
        result = await _advance(hass, result)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HASH_SLUG.replace("_", "-")
    assert result["data"][CONF_ADMIN_TOKEN] == "TESTSECRET"
    assert result["data"][CONF_USE_ADDON] is True
    assert result["data"][CONF_INTEGRATION_CREATED_ADDON] is True
    assert result["data"][CONF_DISCOVERED_SLUG] == HASH_SLUG
    mgr.async_install_addon.assert_awaited_once()


async def test_already_running_skips_install(hass: HomeAssistant) -> None:
    running = _info(
        AddonState.RUNNING,
        hostname="local-usenetstreamer",
        options={"shared_secret": "EXISTING"},
    )
    mgr = _mock_manager([running, running])
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=ADDON_SLUG_LEGACY)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
        patch(
            f"{CF}.async_set_addon_options_safe",
            AsyncMock(return_value={"shared_secret": "EXISTING"}),
        ),
        patch(
            f"{CF}.async_start_addon_safe",
            AsyncMock(),
        ),
        patch.object(UsenetStreamerClient, "async_validate", AsyncMock()),
        patch(
            "custom_components.usenetstreamer.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await _advance(hass, await _init(hass))

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADMIN_TOKEN] == "EXISTING"
    assert result["data"][CONF_INTEGRATION_CREATED_ADDON] is False
    mgr.async_install_addon.assert_not_awaited()


async def test_install_failure_aborts(hass: HomeAssistant) -> None:
    mgr = _mock_manager([_info(AddonState.NOT_INSTALLED)])
    mgr.async_install_addon = AsyncMock(side_effect=AddonError("boom"))
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=HASH_SLUG)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
    ):
        result = await _advance(hass, await _init(hass))

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


# --- new tests for the HassOS writing-fixes spec --------------------------


async def test_safe_set_options_called_with_secret_only(
    hass: HomeAssistant,
) -> None:
    """Configure step should defer the full-options merge to the safe helper."""
    mgr = _mock_manager(
        [
            _info(AddonState.NOT_INSTALLED),
            _info(AddonState.NOT_RUNNING, options={}),
        ]
    )
    safe_set = AsyncMock(return_value={"shared_secret": "XYZ"})
    safe_start = AsyncMock()
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=ADDON_SLUG_LEGACY)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
        patch(f"{CF}.async_set_addon_options_safe", safe_set),
        patch(f"{CF}.async_start_addon_safe", safe_start),
        patch.object(UsenetStreamerClient, "async_validate", AsyncMock()),
        patch(
            "custom_components.usenetstreamer.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await _advance(hass, await _init(hass))
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "configure_addon"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"shared_secret": "XYZ"}
        )
        result = await _advance(hass, result)

    safe_set.assert_awaited_once()
    (passed_mgr, passed_opts) = safe_set.await_args.args
    assert passed_mgr is mgr
    assert passed_opts == {"shared_secret": "XYZ"}
    safe_start.assert_awaited_once()


async def test_finish_aborts_on_invalid_auth(hass: HomeAssistant) -> None:
    running = _info(
        AddonState.RUNNING,
        hostname="local-usenetstreamer",
        options={"shared_secret": "X"},
    )
    mgr = _mock_manager([running])
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=ADDON_SLUG_LEGACY)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
        patch.object(
            UsenetStreamerClient, "async_validate", AsyncMock(side_effect=InvalidAuth)
        ),
    ):
        result = await _advance(hass, await _init(hass))

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_finish_aborts_on_cannot_connect(hass: HomeAssistant) -> None:
    running = _info(
        AddonState.RUNNING,
        hostname="local-usenetstreamer",
        options={"shared_secret": "X"},
    )
    mgr = _mock_manager([running])
    with (
        patch(f"{CF}.is_hassio", return_value=True),
        patch(f"{CF}.async_discover_addon_slug", AsyncMock(return_value=ADDON_SLUG_LEGACY)),
        patch(f"{CF}.get_addon_manager", return_value=mgr),
        patch.object(
            UsenetStreamerClient, "async_validate", AsyncMock(side_effect=CannotConnect)
        ),
    ):
        result = await _advance(hass, await _init(hass))

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_validation_failed"
