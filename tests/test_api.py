"""Tests for the OAuth bridge between Home Assistant and PyViCare."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from requests import Response
from requests.adapters import BaseAdapter

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.viessmann_vitoset.api import HomeAssistantAuth


class FakeServer(BaseAdapter):
    """Answer at the HTTP level, so the real response handling runs."""

    def __init__(self, *responses: tuple[int, bytes]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.requests = []

    def send(self, request, **kwargs) -> Response:
        self.requests.append(request)
        response = Response()
        response.status_code, response._content = self.responses.pop(0)
        response.request = request
        return response

    def close(self) -> None:
        pass


def _auth(hass: HomeAssistant, server: FakeServer, refreshed: str | None = None):
    session = MagicMock(token={"access_token": "old"})

    async def refresh() -> None:
        if refreshed:
            session.token = {"access_token": refreshed}

    session.async_ensure_token_valid = AsyncMock(side_effect=refresh)
    auth = HomeAssistantAuth(hass, session)
    auth.oauth_session.mount("https://", server)
    return auth


EXPIRED = (401, b'{"error": "EXPIRED TOKEN"}')


async def test_expired_token_is_refreshed_and_the_request_retried(
    hass: HomeAssistant,
) -> None:
    server = FakeServer(EXPIRED, (200, b'{"data": []}'))
    auth = _auth(hass, server, refreshed="new")

    result = await hass.async_add_executor_job(auth.get, "/features")

    assert result == {"data": []}
    assert server.requests[-1].headers["Authorization"] == "Bearer new"


async def test_expired_token_that_cannot_be_refreshed_stops_retrying(
    hass: HomeAssistant,
) -> None:
    server = FakeServer(*[EXPIRED] * 5)
    auth = _auth(hass, server)

    with pytest.raises(ConfigEntryAuthFailed):
        await hass.async_add_executor_job(auth.get, "/features")

    assert len(server.requests) == 1


async def test_other_401_starts_reauth(hass: HomeAssistant) -> None:
    auth = _auth(hass, FakeServer((401, b'{"statusCode": 401, "message": "no"}')))

    with pytest.raises(ConfigEntryAuthFailed):
        await hass.async_add_executor_job(auth.get, "/features")


async def test_async_refresh_updates_the_header(hass: HomeAssistant) -> None:
    auth = _auth(hass, FakeServer(), refreshed="new")

    await auth.async_refresh()

    assert auth.oauth_session.headers["Authorization"] == "Bearer new"
