import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings

from .models import AppSettings, NetworkEvent
from .notifications import configured_channels, notify_event


LOGGER = logging.getLogger(__name__)
VERSION_PATTERN = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-+][0-9A-Za-z.-]+)?$")
RELEASES_URL = "https://github.com/hillaliy/LanGuard/releases"


def fetch_latest_version():
    if not settings.LATEST_VERSION_URL:
        return None

    request = urllib.request.Request(
        settings.LATEST_VERSION_URL,
        headers={"User-Agent": "LanGuard"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.VERSION_CHECK_TIMEOUT,
        ) as response:
            response_text = response.read().decode("utf-8").strip()
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        UnicodeDecodeError,
    ) as exc:
        LOGGER.info("Latest version check failed: %s", exc)
        return None

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        latest_version = response_text
    else:
        latest_version = payload.get("version") if isinstance(payload, dict) else None

    if isinstance(latest_version, str) and latest_version.strip():
        return latest_version.strip()
    return None


def normalized_version(value):
    match = VERSION_PATTERN.fullmatch(str(value or "").strip())
    return match.group(1) if match else ""


def is_newer_version(candidate, current):
    candidate_version = normalized_version(candidate)
    current_version = normalized_version(current)
    if not candidate_version or not current_version:
        return False

    candidate_parts = [int(part) for part in candidate_version.split(".")]
    current_parts = [int(part) for part in current_version.split(".")]
    length = max(len(candidate_parts), len(current_parts))
    candidate_parts.extend([0] * (length - len(candidate_parts)))
    current_parts.extend([0] * (length - len(current_parts)))
    return candidate_parts > current_parts


def check_for_version_update():
    config = AppSettings.load()
    if not config.notify_version_updates:
        return {"status": "disabled"}

    latest_version = fetch_latest_version()
    normalized_latest = normalized_version(latest_version)
    if not normalized_latest or not is_newer_version(latest_version, settings.APP_VERSION):
        return {"status": "up_to_date", "latest_version": latest_version}
    if config.last_notified_version == normalized_latest:
        return {"status": "already_notified", "latest_version": normalized_latest}
    if not configured_channels(config):
        return {"status": "no_channels", "latest_version": normalized_latest}

    current_version = normalized_version(settings.APP_VERSION)
    release_url = f"{RELEASES_URL}/tag/v{normalized_latest}"
    event = NetworkEvent.objects.create(
        event_type=NetworkEvent.EventType.VERSION_AVAILABLE,
        message=(
            f"LanGuard {normalized_latest} is available. "
            f"Current version: {current_version}. {release_url}"
        ),
        metadata={
            "current_version": current_version,
            "latest_version": normalized_latest,
            "release_url": release_url,
        },
    )
    deliveries = notify_event(event)
    config.last_notified_version = normalized_latest
    config.save(update_fields=["last_notified_version"])
    return {
        "status": "notified",
        "latest_version": normalized_latest,
        "event_id": event.id,
        "deliveries": len(deliveries),
    }
