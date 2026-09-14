import hashlib
import logging
from urllib.parse import urlparse

import requests
from django.core.cache import cache
from django.db import transaction

from .models import AppSettings, NetworkEvent
from .notifications import notify_event


CACHE_SECONDS = 5 * 60
HEALTH_CHECK_INTERVAL_SECONDS = 5 * 60
LOGGER = logging.getLogger(__name__)


class SpeedtestTrackerError(RuntimeError):
    pass


def normalize_speedtest_tracker_url(value):
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SpeedtestTrackerError(
            "Enter a valid Speedtest Tracker HTTP or HTTPS URL."
        )
    return normalized


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _speed_mbps(payload, name):
    bits = _number(payload.get(f"{name}_bits"))
    if bits is not None:
        return round(bits / 1_000_000, 2)
    value = _number(payload.get(name))
    return round(value, 2) if value is not None else None


def normalize_latest_result(payload, service_url):
    wrapped_result = payload.get("data")
    result = (
        wrapped_result
        if "id" not in payload
        and isinstance(wrapped_result, dict)
        and "id" in wrapped_result
        else payload
    )
    details = result.get("data") if isinstance(result.get("data"), dict) else {}
    packet_loss = result.get("packet_loss")
    if packet_loss is None:
        packet_loss = details.get("packetLoss")

    return {
        "id": result.get("id"),
        "download_mbps": _speed_mbps(result, "download"),
        "upload_mbps": _speed_mbps(result, "upload"),
        "download_display": str(result.get("download_bits_human") or ""),
        "upload_display": str(result.get("upload_bits_human") or ""),
        "ping_ms": _number(result.get("ping")),
        "packet_loss_percent": _number(packet_loss),
        "healthy": result.get("healthy") if isinstance(result.get("healthy"), bool) else None,
        "status": str(result.get("status") or ""),
        "tested_at": result.get("created_at") or details.get("timestamp"),
        "service_url": service_url,
    }


class SpeedtestTrackerClient:
    def __init__(self, base_url, api_token, timeout=10):
        self.base_url = normalize_speedtest_tracker_url(base_url)
        self.api_token = str(api_token or "").strip()
        if not self.api_token:
            raise SpeedtestTrackerError("Enter a Speedtest Tracker API token.")
        self.timeout = timeout

    def latest_result(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/results/latest",
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_token}",
                },
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise SpeedtestTrackerError(
                "Speedtest Tracker did not respond before the timeout."
            ) from exc
        except requests.RequestException as exc:
            response_status = getattr(getattr(exc, "response", None), "status_code", None)
            if response_status in {401, 403}:
                message = "Speedtest Tracker rejected the API token or its permissions."
            elif response_status == 404:
                message = (
                    "Speedtest Tracker has no result available, or the configured URL "
                    "does not expose the results API."
                )
            elif response_status:
                message = f"Speedtest Tracker returned HTTP {response_status}."
            else:
                message = "LanGuard could not connect to Speedtest Tracker."
            raise SpeedtestTrackerError(message) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise SpeedtestTrackerError(
                "Speedtest Tracker returned an unreadable response."
            ) from exc
        if not isinstance(payload, dict):
            raise SpeedtestTrackerError(
                "Speedtest Tracker returned an unexpected response."
            )
        return normalize_latest_result(payload, self.base_url)


def latest_speedtest_result(base_url, api_token, *, force_refresh=False):
    normalized_url = normalize_speedtest_tracker_url(base_url)
    token = str(api_token or "").strip()
    cache_identity = hashlib.sha256(
        f"{normalized_url}\0{token}".encode("utf-8")
    ).hexdigest()
    cache_key = f"languard:speedtest-tracker:latest:{cache_identity}"
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, True

    result = SpeedtestTrackerClient(normalized_url, token).latest_result()
    cache.set(cache_key, result, CACHE_SECONDS)
    return result, False


def _metric(value, suffix):
    if value is None:
        return "-"
    return f"{float(value):.2f}".rstrip("0").rstrip(".") + f" {suffix}"


def check_speedtest_health_change():
    config = AppSettings.load()
    if not config.notify_speedtest_changes:
        return {"status": "disabled"}
    if not (
        config.speedtest_tracker_enabled
        and config.speedtest_tracker_url
        and config.speedtest_tracker_api_token
    ):
        return {"status": "not_configured"}

    source_url = config.speedtest_tracker_url
    source_token = config.speedtest_tracker_api_token
    try:
        result, _ = latest_speedtest_result(
            source_url,
            source_token,
            force_refresh=True,
        )
    except SpeedtestTrackerError as exc:
        LOGGER.info("Speedtest health check could not read the latest result: %s", exc)
        return {"status": "unavailable"}

    result_id = str(result.get("id") or "").strip()
    healthy = result.get("healthy")
    if not result_id:
        return {"status": "invalid_result"}
    if not isinstance(healthy, bool):
        return {"status": "unscored", "result_id": result_id}

    event = None
    with transaction.atomic():
        current = AppSettings.objects.select_for_update().get(pk=config.pk)
        if not (
            current.notify_speedtest_changes
            and current.speedtest_tracker_enabled
            and current.speedtest_tracker_url == source_url
            and current.speedtest_tracker_api_token == source_token
        ):
            return {"status": "configuration_changed"}

        previous_result_id = current.speedtest_last_result_id
        previous_healthy = current.speedtest_last_healthy
        if previous_result_id == result_id and previous_healthy == healthy:
            return {"status": "already_checked", "result_id": result_id}

        current.speedtest_last_result_id = result_id
        current.speedtest_last_healthy = healthy
        current.save(
            update_fields=["speedtest_last_result_id", "speedtest_last_healthy"]
        )

        if not previous_result_id or previous_healthy is None:
            return {"status": "baseline", "result_id": result_id}
        if previous_healthy == healthy:
            return {"status": "unchanged", "result_id": result_id}

        previous_label = "Healthy" if previous_healthy else "Degraded"
        current_label = "Healthy" if healthy else "Degraded"
        metrics = {
            "download_mbps": result.get("download_mbps"),
            "upload_mbps": result.get("upload_mbps"),
            "ping_ms": result.get("ping_ms"),
            "packet_loss_percent": result.get("packet_loss_percent"),
        }
        event = NetworkEvent.objects.create(
            event_type=NetworkEvent.EventType.SPEEDTEST_HEALTH_CHANGED,
            message=(
                f"Speedtest changed from {previous_label} to {current_label}. "
                f"Download: {_metric(metrics['download_mbps'], 'Mbps')}, "
                f"upload: {_metric(metrics['upload_mbps'], 'Mbps')}, "
                f"ping: {_metric(metrics['ping_ms'], 'ms')}, "
                f"packet loss: {_metric(metrics['packet_loss_percent'], '%')}."
            ),
            metadata={
                "result_id": result_id,
                "previous_health": previous_label.lower(),
                "current_health": current_label.lower(),
                "tested_at": result.get("tested_at"),
                "service_url": result.get("service_url") or source_url,
                **metrics,
            },
        )

    deliveries = notify_event(event)
    return {
        "status": "notified",
        "result_id": result_id,
        "health": "healthy" if healthy else "degraded",
        "event_id": event.id,
        "deliveries": len(deliveries),
    }
