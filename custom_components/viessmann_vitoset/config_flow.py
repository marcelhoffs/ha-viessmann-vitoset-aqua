"""Config flow for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .api import API_ERRORS, HomeAssistantAuth, find_softener
from .const import DOMAIN


class VitosetConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Log in to the Viessmann account through OAuth2."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        # The token was issued just now, so this auth never has to refresh it.
        auth = HomeAssistantAuth(self.hass, SimpleNamespace(token=data["token"]))
        try:
            softener = await self.hass.async_add_executor_job(find_softener, auth)
        except (ConfigEntryAuthFailed, *API_ERRORS):
            self.logger.exception("Could not read the Viessmann account")
            return self.async_abort(reason="cannot_connect")
        if softener is None:
            return self.async_abort(reason="no_softener")

        # The softener identifies the entry: the API scopes in use don't expose
        # the account itself.
        await self.async_set_unique_id(softener.accessor.serial)
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            if entry.unique_id is not None:
                self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                entry, unique_id=self.unique_id, data_updates=data
            )
        return self.async_create_entry(title="Vitoset Aqua", data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
