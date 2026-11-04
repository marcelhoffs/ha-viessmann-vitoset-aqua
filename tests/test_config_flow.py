"""Tests for the Viessmann Vitoset Aqua OAuth2 config flow."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from PyViCare.PyViCareAbstractOAuthManager import TOKEN_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from custom_components.viessmann_vitoset.const import DOMAIN

TOKEN = {
    "access_token": "new-token",
    "refresh_token": "new-refresh",
    "token_type": "Bearer",
    "expires_in": 3600,
}


async def _credentials(hass: HomeAssistant) -> None:
    await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client-id", "", "Viessmann")
    )


async def _authorize(hass, hass_client_no_auth, aioclient_mock, result) -> dict:
    """Walk the external OAuth step; return the authorize query for assertions."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    query = parse_qs(urlparse(result["url"]).query)
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=TOKEN)
    return query


async def test_user_flow_requests_pkce_and_scopes(
    hass: HomeAssistant, hass_client_no_auth, aioclient_mock, current_request_with_host
) -> None:
    await _credentials(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    query = await _authorize(hass, hass_client_no_auth, aioclient_mock, result)
    assert query["scope"] == ["IoT offline_access"]
    assert query["code_challenge_method"] == ["S256"]

    with patch(
        "custom_components.viessmann_vitoset.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["token"]["access_token"] == "new-token"


async def test_second_entry_is_refused(hass: HomeAssistant) -> None:
    await _credentials(hass)
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_updates_the_token(
    hass: HomeAssistant, hass_client_no_auth, aioclient_mock, current_request_with_host
) -> None:
    await _credentials(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {"access_token": "old"}},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    await _authorize(hass, hass_client_no_auth, aioclient_mock, result)
    with patch(
        "custom_components.viessmann_vitoset.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "new-token"
