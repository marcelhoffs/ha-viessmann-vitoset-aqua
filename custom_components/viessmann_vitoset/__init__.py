"""The Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .api import API_ERRORS, HomeAssistantAuth, find_softener
from .const import DOMAIN
from .coordinator import VitosetConfigEntry, VitosetCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
ICONS_URL = f"/{DOMAIN}/icons.js"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the custom icon to the frontend."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(ICONS_URL, str(Path(__file__).parent / "icons.js"), False)]
    )
    add_extra_js_url(hass, ICONS_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VitosetConfigEntry) -> bool:
    """Set up the softener from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    auth = HomeAssistantAuth(hass, session)
    try:
        softener = await hass.async_add_executor_job(find_softener, auth)
    except API_ERRORS as err:
        raise ConfigEntryNotReady(f"Error communicating with ViCare: {err}") from err
    if softener is None:
        # The login flow checked for one, so this is likely a passing API hiccup.
        raise ConfigEntryNotReady("No water softener found on this Viessmann account")

    # Entries from before reauth checked the account have no unique ID.
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=softener.accessor.serial
        )

    coordinator = VitosetCoordinator(hass, entry, softener, auth)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitosetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
