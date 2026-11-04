"""Bridge between Home Assistant's OAuth2 session and PyViCare."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotPaidForError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from PyViCare.PyViCareWaterTreatment import WaterTreatment
import requests

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

# PACKAGE_NOT_PAID_FOR is NotPaidFor on a direct request, and NotSupportedFeature
# once it has passed through PyViCare's feature cache.
API_ERRORS = (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotPaidForError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)


def _raise_on_rejected_token(response: requests.Response, **_: Any) -> None:
    """Start reauth on a 401, which PyViCare would report as invalid data."""
    if response.status_code == 401 and "EXPIRED TOKEN" not in response.text:
        raise ConfigEntryAuthFailed("ViCare rejected the access token")


class HomeAssistantAuth(AbstractViCareOAuthManager):
    """Give PyViCare the token held by a Home Assistant config entry."""

    def __init__(self, hass: HomeAssistant, session: OAuth2Session) -> None:
        self._hass = hass
        self._session = session
        http = requests.Session()
        http.headers["Authorization"] = self._bearer()
        http.hooks["response"].append(_raise_on_rejected_token)
        super().__init__(http)

    async def async_refresh(self) -> None:
        """Refresh the token if it is due."""
        await self._session.async_ensure_token_valid()
        self.oauth_session.headers["Authorization"] = self._bearer()

    def renewToken(self) -> None:
        """Handle an expired token; PyViCare calls this from an executor thread."""
        expired = self._session.token["access_token"]
        run_coroutine_threadsafe(self.async_refresh(), self._hass.loop).result()
        # PyViCare retries after this, without limit, so an unchanged token
        # has to stop here or it would loop until the API quota runs out.
        if self._session.token["access_token"] == expired:
            raise ConfigEntryAuthFailed("ViCare rejected an unexpired token")

    def _bearer(self) -> str:
        return f"Bearer {self._session.token['access_token']}"


def find_softener(auth: AbstractViCareOAuthManager) -> WaterTreatment | None:
    """Return the account's softener, if it has one."""
    vicare = PyViCare()
    vicare.initWithExternalOAuth(auth)
    # vicare.devices leaves out WaterSoftener, so search all_devices.
    # shortcut: uses the first softener on the account, split into a coordinator
    # per device if someone with two ever needs it.
    for device in vicare.all_devices:
        if device.getDeviceType() == "WaterSoftener":
            return device.asWaterTreatment()
    return None
