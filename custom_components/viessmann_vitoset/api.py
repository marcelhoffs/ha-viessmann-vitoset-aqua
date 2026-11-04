"""Bridge between Home Assistant's OAuth2 session and PyViCare."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe

from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

# PACKAGE_NOT_PAID_FOR surfaces as NotSupportedFeature on a full feature fetch.
API_ERRORS = (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)


class HomeAssistantAuth(AbstractViCareOAuthManager):
    """Give PyViCare the token held by a Home Assistant config entry."""

    def __init__(self, hass: HomeAssistant, session: OAuth2Session) -> None:
        self._hass = hass
        self._session = session
        http = requests.Session()
        http.headers["Authorization"] = self._bearer()
        super().__init__(http)

    def renewToken(self) -> None:
        """Refresh the token; PyViCare calls this from an executor thread."""
        run_coroutine_threadsafe(
            self._session.async_ensure_token_valid(), self._hass.loop
        ).result()
        self.oauth_session.headers["Authorization"] = self._bearer()

    def _bearer(self) -> str:
        return f"Bearer {self._session.token['access_token']}"
