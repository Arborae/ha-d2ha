"""Map D2HA error codes onto translated messages."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

# The codes of API.md ({"error": "<code>"}) and the job error keys (job["error"]).
ERROR_KEYS = {
    "bad_request": "api_bad_request",
    "self_update": "api_self_update",
    "proxy_update": "api_proxy_update",
    "unauthorized": "api_unauthorized",
    "csrf": "api_csrf",
    "read_only": "api_read_only",
    "not_found": "api_not_found",
    "no_notes": "api_no_notes",
    "nothing_to_update": "api_nothing_to_update",
    "rate_limited": "api_rate_limited",
    "error.pull_failed": "job_pull_failed",
    "error.recreate_failed": "job_recreate_failed",
    "error.no_tag": "job_no_tag",
    "error.not_found": "job_not_found",
}


def d2ha_error(fallback_key: str, code: str) -> HomeAssistantError:
    """A translated error for a known D2HA code, the fallback with the code otherwise."""
    key = ERROR_KEYS.get(code)
    if key is not None:
        return HomeAssistantError(translation_domain=DOMAIN, translation_key=key)
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=fallback_key,
        translation_placeholders={"error": code},
    )
