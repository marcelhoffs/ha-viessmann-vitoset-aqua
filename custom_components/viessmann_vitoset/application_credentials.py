"""Application credentials platform for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from PyViCare.PyViCareAbstractOAuthManager import (
    AUTHORIZE_URL,
    SCOPE_IOT,
    SCOPE_OFFLINE_ACCESS,
    TOKEN_URL,
)

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return the links shown in the credentials dialog."""
    return {
        "developer_portal": "https://app.developer.viessmann-climatesolutions.com",
        "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
    }


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> VitosetOAuth2Implementation:
    """Return the PKCE auth implementation; Viessmann clients have no secret."""
    return VitosetOAuth2Implementation(
        hass, auth_domain, credential.client_id, AUTHORIZE_URL, TOKEN_URL
    )


class VitosetOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """OAuth2 implementation that requests the ViCare scopes."""

    @property
    def extra_authorize_data(self) -> dict:
        return super().extra_authorize_data | {
            "scope": f"{SCOPE_IOT} {SCOPE_OFFLINE_ACCESS}"
        }
