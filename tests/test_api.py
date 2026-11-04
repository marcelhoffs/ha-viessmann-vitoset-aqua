"""Tests for the OAuth bridge between Home Assistant and PyViCare."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.viessmann_vitoset.api import HomeAssistantAuth


def _response(body: dict) -> MagicMock:
    return MagicMock(status_code=200, json=MagicMock(return_value=body))


async def test_expired_token_is_refreshed_and_the_request_retried(
    hass: HomeAssistant,
) -> None:
    session = MagicMock(token={"access_token": "old"})

    async def refresh() -> None:
        session.token = {"access_token": "new"}

    session.async_ensure_token_valid = AsyncMock(side_effect=refresh)
    auth = HomeAssistantAuth(hass, session)
    assert auth.oauth_session.headers["Authorization"] == "Bearer old"

    responses = [_response({"error": "EXPIRED TOKEN"}), _response({"data": []})]
    with patch.object(auth.oauth_session, "get", side_effect=responses):
        result = await hass.async_add_executor_job(auth.get, "/features")

    assert result == {"data": []}
    assert auth.oauth_session.headers["Authorization"] == "Bearer new"
