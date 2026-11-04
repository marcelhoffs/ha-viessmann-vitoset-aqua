# Viessmann Vitoset Aqua for Home Assistant

Brings the Viessmann Vitoset Aqua water softener into Home Assistant through
the ViCare cloud API. It shows up in the ViCare app, but Home Assistant's own
[ViCare integration](https://www.home-assistant.io/integrations/vicare/) doesn't
support it yet ([core#190448](https://github.com/home-assistant/core/issues/190448)).
Both integrations can run side by side. Once core supports the softener, this
one can go.

Tested against the data of a `VitosetAqua87S`.

## Entities

| Entity | Notes |
| --- | --- |
| Salt days remaining | |
| Water consumption total | Use this one in the Energy dashboard |
| Water consumption today, last 7 days | Don't add these to the Energy dashboard, they'd double count |
| Water flow | Refreshed every 5 minutes, so a snapshot and not a live reading |
| Shutoff valve position | |
| Holiday mode | |
| Leak sensor N | One per paired sensor, plus battery and signal strength (off by default). Reload the integration after pairing a new sensor |
| Low salt alert threshold, maximum water flow, shutoff valve motor | Diagnostic |

Everything is read-only: the API offers no commands for this device, so the
valve can't be operated from Home Assistant.

## Setup

1. Install through HACS: add `https://github.com/marcelhoffs/ha-viessmann-vitoset-aqua`
   as a custom repository (type *Integration*), download it and restart Home
   Assistant.
2. Create an API client at the
   [Viessmann developer portal](https://app.developer.viessmann-climatesolutions.com)
   with redirect URI `https://my.home-assistant.io/redirect/oauth`. If you already
   have a client for the ViCare integration you can reuse it, but they then
   share the same API quota.
3. Add the integration under Settings → Devices & Services. Enter the client ID;
   the client secret is ignored, so enter any value. Log in with your Viessmann
   account.

## Development

    python -m venv .venv
    .venv/bin/pip install -r requirements_test.txt
    .venv/bin/pytest
