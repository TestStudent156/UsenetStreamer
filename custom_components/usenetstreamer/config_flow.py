"""Config flow for UsenetStreamer.

Supervisor-only, single instance. The flow:

1. Confirms the host is Supervised (``is_hassio``).
2. Discovers the actual add-on slug via the Supervisor API, since
   store-installed copies are slugged as ``local_<hash>_usenetstreamer``
   (Supervisor hashes the repository URL on ``store.add_repository``).
3. Installs / configures / starts the add-on if needed.
4. Validates the connection to the running add-on **before** creating the
   config entry, so a doomed setup never reaches the entry.

Modelled on the Z-Wave JS add-on flow.
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

from . import addon
from .addon import (
    async_discover_addon_slug,
    async_set_addon_options_safe,
    async_start_addon_safe,
    get_addon_manager,
)
from .api import CannotConnect, InvalidAuth, UsenetStreamerClient
from .const import (
    ADDON_NAME,
    ADDON_SLUG_LEGACY,
    CONF_ADMIN_TOKEN,
    CONF_DISCOVERED_SLUG,
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


def _slug_to_hostname(slug: str) -> str:
    """Best-effort hostname for a slug: replace underscores with dashes."""
    return slug.replace("_", "-")


class UsenetStreamerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Install and configure the UsenetStreamer add-on."""

    VERSION = 1

    def __init__(self) -> None:
        self.shared_secret: str | None = None
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.discovered_slug: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        self.discovered_slug = await async_discover_addon_slug(self.hass)
        if not self.discovered_slug:
            return self.async_abort(reason="addon_not_found")
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
        if not self.discovered_slug:
            # The user step always sets this; treat as a programmer error.
            raise AbortFlow("addon_not_found")
        try:
            return await get_addon_manager(
                self.hass, self.discovered_slug
            ).async_get_addon_info()
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
        await get_addon_manager(
            self.hass, self.discovered_slug or ADDON_SLUG_LEGACY
        ).async_install_addon()

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="addon_install_failed")

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self.shared_secret = user_input[CONF_SHARED_SECRET]
            try:
                await async_set_addon_options_safe(
                    get_addon_manager(
                        self.hass, self.discovered_slug or ADDON_SLUG_LEGACY
                    ),
                    {CONF_SHARED_SECRET: self.shared_secret},
                )
            except AddonError as err:
                return self.async_show_form(
                    step_id="configure_addon",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_SHARED_SECRET,
                                default=self.shared_secret,
                            ): cv.string
                        }
                    ),
                    errors={"base": "addon_options_write_failed"},
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
        await async_start_addon_safe(
            get_addon_manager(
                self.hass, self.discovered_slug or ADDON_SLUG_LEGACY
            )
        )

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="addon_start_failed")

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Build the connection and validate it before creating the entry."""
        assert self.shared_secret is not None  # set in previous step
        assert self.discovered_slug is not None
        addon_info = await self._async_get_addon_info()
        host = addon_info.hostname or _slug_to_hostname(self.discovered_slug)

        client = UsenetStreamerClient(
            hass=self.hass,
            host=host,
            port=DEFAULT_PORT,
            ssl=False,
            admin_token=self.shared_secret,
            verify_ssl=True,
        )
        try:
            await client.async_validate()
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="addon_validation_failed")

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
                CONF_DISCOVERED_SLUG: self.discovered_slug,
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
