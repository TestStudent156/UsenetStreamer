"""Config flow for UsenetStreamer.

Supervisor-only, single instance: the flow installs, configures, and starts the
UsenetStreamer add-on, then connects to it. Modelled on the Z-Wave JS add-on flow.
"""
from __future__ import annotations

import asyncio
import secrets
from typing import Any

import voluptuous as vol
from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.hassio import is_hassio

from .addon import get_addon_manager
from .const import (
    ADDON_NAME,
    ADDON_SLUG,
    CONF_ADMIN_TOKEN,
    CONF_HOST,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USE_ADDON,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

CONF_SHARED_SECRET = "shared_secret"


class UsenetStreamerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Install and configure the UsenetStreamer add-on."""

    VERSION = 1

    def __init__(self) -> None:
        self.shared_secret: str | None = None
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_installation()

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Route based on the current add-on state."""
        addon_info = await self._async_get_addon_info()
        if addon_info.state is AddonState.RUNNING and addon_info.options.get(
            CONF_SHARED_SECRET
        ):
            self.shared_secret = addon_info.options[CONF_SHARED_SECRET]
            return await self.async_step_finish_addon_setup()
        if addon_info.state in (AddonState.RUNNING, AddonState.NOT_RUNNING):
            return await self.async_step_configure_addon()
        return await self.async_step_install_addon()

    async def _async_get_addon_info(self) -> AddonInfo:
        try:
            return await get_addon_manager(self.hass).async_get_addon_info()
        except AddonError as err:
            raise AbortFlow("addon_info_failed") from err

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self.install_task is None:
            self.install_task = self.hass.async_create_task(
                self._async_install_addon()
            )
        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                progress_task=self.install_task,
            )
        try:
            await self.install_task
        except AddonError:
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None
        self.integration_created_addon = True
        return self.async_show_progress_done(next_step_id="configure_addon")

    async def _async_install_addon(self) -> None:
        await get_addon_manager(self.hass).async_install_addon()

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="addon_install_failed")

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self.shared_secret = user_input[CONF_SHARED_SECRET]
            await get_addon_manager(self.hass).async_set_addon_options(
                {CONF_SHARED_SECRET: self.shared_secret}
            )
            return await self.async_step_start_addon()
        default_secret = self.shared_secret or secrets.token_hex(16)
        return self.async_show_form(
            step_id="configure_addon",
            data_schema=vol.Schema(
                {vol.Required(CONF_SHARED_SECRET, default=default_secret): cv.string}
            ),
        )

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self.start_task is None:
            self.start_task = self.hass.async_create_task(self._async_start_addon())
        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                progress_task=self.start_task,
            )
        try:
            await self.start_task
        except AddonError:
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None
        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def _async_start_addon(self) -> None:
        await get_addon_manager(self.hass).async_start_addon()

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="addon_start_failed")

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        addon_info = await self._async_get_addon_info()
        host = addon_info.hostname or ADDON_SLUG.replace("_", "-")
        return self.async_create_entry(
            title=ADDON_NAME,
            data={
                CONF_HOST: host,
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_ADMIN_TOKEN: self.shared_secret,
                CONF_USE_ADDON: True,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return UsenetStreamerOptionsFlow()


class UsenetStreamerOptionsFlow(OptionsFlow):
    """Handle options (scan interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    cv.positive_int, vol.Range(min=5)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
