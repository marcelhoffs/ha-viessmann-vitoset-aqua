"""The Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareUtils import PyViCareInvalidCredentialsError
from PyViCare.PyViCareWaterTreatment import WaterTreatment

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import API_ERRORS, HomeAssistantAuth
from .coordinator import VitosetConfigEntry, VitosetCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


def _find_softener(auth: HomeAssistantAuth) -> WaterTreatment | None:
    vicare = PyViCare()
    vicare.initWithExternalOAuth(auth)
    # vicare.devices leaves out WaterSoftener, so search all_devices.
    # shortcut: uses the first softener on the account, split into a coordinator
    # per device if someone with two ever needs it.
    for device in vicare.all_devices:
        if device.getDeviceType() == "WaterSoftener":
            return device.asWaterTreatment()
    return None


async def async_setup_entry(hass: HomeAssistant, entry: VitosetConfigEntry) -> bool:
    """Set up the softener from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    auth = HomeAssistantAuth(hass, session)
    try:
        softener = await hass.async_add_executor_job(_find_softener, auth)
    except PyViCareInvalidCredentialsError as err:
        raise ConfigEntryAuthFailed from err
    except API_ERRORS as err:
        raise ConfigEntryNotReady(f"Error communicating with ViCare: {err}") from err
    if softener is None:
        raise ConfigEntryError("No water softener found on this Viessmann account")

    coordinator = VitosetCoordinator(hass, entry, softener)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitosetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
