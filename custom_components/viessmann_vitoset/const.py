"""Constants for the Viessmann Vitoset Aqua integration."""
from datetime import timedelta

DOMAIN = "viessmann_vitoset"

# One API call per poll. The ViCare API quota is shared with anything else
# using the same client ID, such as Home Assistant's own ViCare integration.
SCAN_INTERVAL = timedelta(minutes=5)
