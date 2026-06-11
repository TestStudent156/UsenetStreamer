"""Supervisor add-on management for UsenetStreamer.

The integration no longer assumes the add-on is at the literal slug
``local_usenetstreamer``; store-installed copies are slugged as
``local_<hash>_usenetstreamer`` (Supervisor hashes the repository URL on
``store.add_repository``). At config-flow time we ask the Supervisor for the
list of installed add-ons and match the suffix ``_usenetstreamer``. The
discovered slug is persisted on the config entry so subsequent setup calls
don't have to re-enumerate.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.hassio import async_send_hassio_command

from .const import (
    ADDON_NAME,
    ADDON_SLUG_LEGACY,
    ADDON_SLUG_SUFFIX,
    DOMAIN,
    OPTIONS_WRITE_BASE_BACKOFF,
    OPTIONS_WRITE_MAX_RETRIES,
)

LOGGER = logging.getLogger(__name__)


def get_addon_manager(hass: HomeAssistant, slug: str) -> AddonManager:
    """Return an :class:`AddonManager` for the given slug.

    The manager is a thin wrapper over the Supervisor HTTP API; we don't
    memoize it because we want a per-slug instance once we've discovered the
    real slug.
    """
    return AddonManager(hass, LOGGER, ADDON_NAME, slug)


async def async_discover_addon_slug(hass: HomeAssistant) -> str | None:
    """Find the installed UsenetStreamer add-on by suffix-matching the slug.

    Returns the first add-on whose slug ends with ``_usenetstreamer``, or
    ``None`` if none is installed (or the Supervisor isn't reachable). The
    legacy literal slug is intentionally *not* included in the match — if
    the user has a legacy local add-on at ``local_usenetstreamer`` it will
    also be matched by the suffix, which is what we want.
    """
    try:
        data = await async_send_hassio_command(hass, "addons")
    except (OSError, asyncio.TimeoutError, ValueError, TypeError) as err:
        # Supervisor / WebSocket transport errors and JSON decode errors. We
        # intentionally do NOT catch ``Exception`` here — letting unexpected
        # errors propagate surfaces real bugs in the caller (and in the
        # config flow they map to a specific abort reason).
        LOGGER.debug("Supervisor /addons not reachable during discovery: %s", err)
        return None

    addons: list[dict[str, Any]]
    if isinstance(data, dict):
        addons = list(data.get("addons", []))
    elif isinstance(data, list):
        addons = data
    else:
        return None

    for addon in addons:
        slug = str(addon.get("slug", ""))
        if slug.endswith(ADDON_SLUG_SUFFIX):
            return slug
    return None


async def async_ensure_addon_running(
    hass: HomeAssistant, slug: str
) -> AddonInfo:
    """Make sure the add-on at ``slug`` is installed and running.

    Raises :class:`ConfigEntryNotReady` (so HA retries setup) while the
    add-on is missing, installing, or still starting. The slug is included
    in the retry message so a misconfigured user can see which one HA is
    looking for.
    """
    addon_manager = get_addon_manager(hass, slug)
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        raise ConfigEntryNotReady(
            f"Could not read info for add-on {slug!r}: {err}"
        ) from err

    if addon_info.state is AddonState.NOT_INSTALLED:
        raise ConfigEntryNotReady(f"UsenetStreamer add-on {slug!r} is not installed")
    if addon_info.state in (AddonState.INSTALLING, AddonState.UPDATING):
        raise ConfigEntryNotReady(f"UsenetStreamer add-on {slug!r} is installing")
    if addon_info.state is AddonState.NOT_RUNNING:
        addon_manager.async_schedule_start_addon()
        raise ConfigEntryNotReady(f"UsenetStreamer add-on {slug!r} is starting")
    return addon_info


async def async_set_addon_options_safe(
    addon_manager: AddonManager, options_to_set: dict[str, Any]
) -> dict[str, Any]:
    """Write ``options_to_set`` to the add-on, preserving all unspecified keys.

    The Supervisor requires the full options dict on every write, so we
    fetch the current options first and merge. Retries with exponential
    backoff on transient :class:`AddonError`s and re-raises the last error
    if all attempts fail. Returns the merged options that were written.
    """
    merged: dict[str, Any] = dict(options_to_set)
    last_err: AddonError | None = None
    for attempt in range(OPTIONS_WRITE_MAX_RETRIES):
        try:
            current = await addon_manager.async_get_addon_info()
            merged = {**current.options, **options_to_set}
            await addon_manager.async_set_addon_options(merged)
            return merged
        except AddonError as err:
            last_err = err
            if attempt < OPTIONS_WRITE_MAX_RETRIES - 1:
                backoff = OPTIONS_WRITE_BASE_BACKOFF * (2 ** attempt)
                LOGGER.debug(
                    "Set add-on options attempt %d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    err,
                    backoff,
                )
                await asyncio.sleep(backoff)
    assert last_err is not None  # always set when the loop exits without return
    raise last_err


async def async_start_addon_safe(addon_manager: AddonManager) -> None:
    """Start the add-on, retrying transient :class:`AddonError`s with backoff."""
    last_err: AddonError | None = None
    for attempt in range(OPTIONS_WRITE_MAX_RETRIES):
        try:
            await addon_manager.async_start_addon()
            return
        except AddonError as err:
            last_err = err
            if attempt < OPTIONS_WRITE_MAX_RETRIES - 1:
                backoff = OPTIONS_WRITE_BASE_BACKOFF * (2 ** attempt)
                LOGGER.debug(
                    "Start add-on attempt %d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    err,
                    backoff,
                )
                await asyncio.sleep(backoff)
    assert last_err is not None
    raise last_err


__all__ = [
    "async_discover_addon_slug",
    "async_ensure_addon_running",
    "async_set_addon_options_safe",
    "async_start_addon_safe",
    "get_addon_manager",
]
