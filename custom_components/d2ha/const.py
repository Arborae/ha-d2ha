"""Constants for the D2HA integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "d2ha"

CONF_URL: Final = "url"
CONF_TOKEN: Final = "token"

SCAN_INTERVAL: Final = timedelta(seconds=60)
SCAN_INTERVAL_ACTIVE: Final = timedelta(seconds=5)
# How long a container must be missing before its device is removed.
REMOVE_AFTER: Final = timedelta(hours=24)

API_BASE: Final = "/api/v1"
REQUEST_TIMEOUT: Final = 15
JOB_POLL_INTERVAL: Final = 1.5
JOB_TIMEOUT: Final = 30 * 60
