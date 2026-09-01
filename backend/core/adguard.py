import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta, timezone as datetime_timezone
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AdGuardUnmatchedClient, AppSettings, Device, DeviceDNSActivity
from .user_messages import stored_error_message


LOGGER = logging.getLogger(__name__)
QUERY_PAGE_SIZE = 500
MAX_SYNC_ENTRIES = 5000
BLOCKED_REASONS = {
    "FilteredBlackList",
    "FilteredSafeBrowsing",
    "FilteredParental",
    "FilteredInvalid",
    "FilteredSafeSearch",
    "FilteredBlockedService",
}


class AdGuardError(RuntimeError):
    pass


def normalize_adguard_url(value):
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AdGuardError("Enter a valid AdGuard Home HTTP or HTTPS URL.")
    return normalized


class AdGuardClient:
    def __init__(self, base_url, username="", password="", timeout=10):
        self.base_url = normalize_adguard_url(base_url)
        self.control_url = (
            self.base_url
            if self.base_url.endswith("/control")
            else f"{self.base_url}/control"
        )
        self.auth = (username, password) if username else None
        self.timeout = timeout

    def _get(self, path, params=None):
        try:
            response = requests.get(
                f"{self.control_url}/{path.lstrip('/')}",
                params=params,
                auth=self.auth,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise AdGuardError("AdGuard Home did not respond before the timeout.") from exc
        except requests.RequestException as exc:
            response_status = getattr(getattr(exc, "response", None), "status_code", None)
            if response_status in {401, 403}:
                message = "AdGuard Home rejected the username or password."
            elif response_status:
                message = f"AdGuard Home returned HTTP {response_status}."
            else:
                message = "LanGuard could not connect to AdGuard Home."
            raise AdGuardError(message) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise AdGuardError("AdGuard Home returned an unreadable response.") from exc

    def status(self):
        return self._get("status")

    def query_log_config(self):
        return self._get("querylog/config")

    def query_log(self, offset=0, limit=QUERY_PAGE_SIZE):
        return self._get("querylog", params={"offset": offset, "limit": limit})


def test_adguard_connection(base_url, username="", password=""):
    client = AdGuardClient(base_url, username, password)
    server_status = client.status()
    query_log_config = client.query_log_config()
    if not query_log_config.get("enabled"):
        raise AdGuardError("Enable the query log in AdGuard Home before syncing.")
    return {
        "version": str(server_status.get("version") or ""),
        "running": bool(server_status.get("running", True)),
        "protection_enabled": bool(server_status.get("protection_enabled")),
        "query_log_enabled": bool(query_log_config.get("enabled")),
    }


def parse_query_time(value):
    parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    parsed = parsed.astimezone(datetime_timezone.utc)
    if not settings.USE_TZ:
        return timezone.make_naive(parsed, datetime_timezone.utc)
    return parsed


def normalize_domain(value):
    return str(value or "").strip().rstrip(".").lower()[:253]


@dataclass
class ActivityAggregate:
    device: Device
    domain: str
    query_type: str
    first_seen: object
    last_seen: object
    query_count: int = 0
    blocked_count: int = 0
    last_status: str = ""
    last_reason: str = ""
    last_service_name: str = ""

    def add(self, seen_at, blocked, status, reason, service_name):
        self.query_count += 1
        self.blocked_count += int(blocked)
        self.first_seen = min(self.first_seen, seen_at)
        if seen_at >= self.last_seen:
            self.last_seen = seen_at
            self.last_status = status[:32]
            self.last_reason = reason[:64]
            self.last_service_name = service_name[:128]


@dataclass
class UnmatchedClientAggregate:
    client: str
    first_seen: object
    last_seen: object
    query_count: int = 0
    blocked_count: int = 0
    last_domain: str = ""
    last_status: str = ""
    last_reason: str = ""

    def add(self, seen_at, domain, blocked, status, reason):
        self.query_count += 1
        self.blocked_count += int(blocked)
        self.first_seen = min(self.first_seen, seen_at)
        if seen_at >= self.last_seen:
            self.last_seen = seen_at
            self.last_domain = domain[:253]
            self.last_status = status[:32]
            self.last_reason = reason[:64]


def _save_aggregates(aggregates, unmatched_aggregates, matched_clients):
    with transaction.atomic():
        for aggregate in aggregates.values():
            activity, created = DeviceDNSActivity.objects.get_or_create(
                device=aggregate.device,
                domain=aggregate.domain,
                query_type=aggregate.query_type,
                defaults={
                    "query_count": aggregate.query_count,
                    "blocked_count": aggregate.blocked_count,
                    "first_seen": aggregate.first_seen,
                    "last_seen": aggregate.last_seen,
                    "last_status": aggregate.last_status,
                    "last_reason": aggregate.last_reason,
                    "last_service_name": aggregate.last_service_name,
                },
            )
            if created:
                continue
            DeviceDNSActivity.objects.filter(pk=activity.pk).update(
                query_count=F("query_count") + aggregate.query_count,
                blocked_count=F("blocked_count") + aggregate.blocked_count,
                first_seen=min(activity.first_seen, aggregate.first_seen),
                last_seen=max(activity.last_seen, aggregate.last_seen),
                last_status=(
                    aggregate.last_status
                    if aggregate.last_seen >= activity.last_seen
                    else activity.last_status
                ),
                last_reason=(
                    aggregate.last_reason
                    if aggregate.last_seen >= activity.last_seen
                    else activity.last_reason
                ),
                last_service_name=(
                    aggregate.last_service_name
                    if aggregate.last_seen >= activity.last_seen
                    else activity.last_service_name
                ),
            )

        for aggregate in unmatched_aggregates.values():
            unmatched, created = AdGuardUnmatchedClient.objects.get_or_create(
                client=aggregate.client,
                defaults={
                    "query_count": aggregate.query_count,
                    "blocked_count": aggregate.blocked_count,
                    "first_seen": aggregate.first_seen,
                    "last_seen": aggregate.last_seen,
                    "last_domain": aggregate.last_domain,
                    "last_status": aggregate.last_status,
                    "last_reason": aggregate.last_reason,
                },
            )
            if created:
                continue
            AdGuardUnmatchedClient.objects.filter(pk=unmatched.pk).update(
                query_count=F("query_count") + aggregate.query_count,
                blocked_count=F("blocked_count") + aggregate.blocked_count,
                first_seen=min(unmatched.first_seen, aggregate.first_seen),
                last_seen=max(unmatched.last_seen, aggregate.last_seen),
                last_domain=(
                    aggregate.last_domain
                    if aggregate.last_seen >= unmatched.last_seen
                    else unmatched.last_domain
                ),
                last_status=(
                    aggregate.last_status
                    if aggregate.last_seen >= unmatched.last_seen
                    else unmatched.last_status
                ),
                last_reason=(
                    aggregate.last_reason
                    if aggregate.last_seen >= unmatched.last_seen
                    else unmatched.last_reason
                ),
            )

        if matched_clients:
            AdGuardUnmatchedClient.objects.filter(client__in=matched_clients).delete()


def cleanup_adguard_activity(retention_days):
    cutoff = timezone.now() - timedelta(days=max(int(retention_days), 1))
    _, activity_details = DeviceDNSActivity.objects.filter(last_seen__lt=cutoff).delete()
    _, unmatched_details = AdGuardUnmatchedClient.objects.filter(
        last_seen__lt=cutoff
    ).delete()
    return {
        "activity": activity_details.get("core.DeviceDNSActivity", 0),
        "unmatched_clients": unmatched_details.get("core.AdGuardUnmatchedClient", 0),
    }


def sync_adguard_query_log(config=None, max_entries=MAX_SYNC_ENTRIES):
    config = config or AppSettings.load()
    if not config.adguard_enabled:
        return {"status": "disabled", "processed": 0, "matched": 0, "unmatched": 0}
    if not config.adguard_url:
        raise AdGuardError("Configure the AdGuard Home URL before syncing.")

    client = AdGuardClient(
        config.adguard_url,
        config.adguard_username,
        config.adguard_password,
    )
    cursor = config.adguard_last_sync_at
    devices_by_ip = {}
    for device in Device.objects.order_by("ip", "-lastseen"):
        devices_by_ip.setdefault(device.ip, device)
    aggregates = {}
    unmatched_aggregates = {}
    matched_clients = set()
    processed = 0
    matched = 0
    unmatched = 0
    invalid = 0
    offset = 0
    reached_cursor = False
    newest_seen = cursor

    try:
        if not client.query_log_config().get("enabled"):
            raise AdGuardError("Enable the query log in AdGuard Home before syncing.")
        while offset < max_entries and not reached_cursor:
            payload = client.query_log(offset=offset, limit=QUERY_PAGE_SIZE)
            entries = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                break

            for item in entries:
                if processed >= max_entries:
                    break
                seen_at = parse_query_time(item.get("time"))
                if seen_at is None:
                    invalid += 1
                    continue
                if cursor and seen_at <= cursor:
                    reached_cursor = True
                    break

                processed += 1
                newest_seen = max(newest_seen, seen_at) if newest_seen else seen_at
                client_value = str(item.get("client") or "").strip()
                device = devices_by_ip.get(client_value)
                question = item.get("question") if isinstance(item.get("question"), dict) else {}
                domain = normalize_domain(question.get("name"))
                if device is None or not domain:
                    unmatched += 1
                    if device is None and client_value and domain:
                        reason = str(item.get("reason") or "")
                        aggregate = unmatched_aggregates.get(client_value)
                        if aggregate is None:
                            aggregate = UnmatchedClientAggregate(
                                client=client_value[:255],
                                first_seen=seen_at,
                                last_seen=seen_at,
                            )
                            unmatched_aggregates[client_value] = aggregate
                        aggregate.add(
                            seen_at,
                            domain,
                            reason in BLOCKED_REASONS,
                            str(item.get("status") or ""),
                            reason,
                        )
                    continue

                matched += 1
                matched_clients.add(client_value)
                query_type = str(question.get("type") or "").strip().upper()[:16]
                reason = str(item.get("reason") or "")
                key = (device.pk, domain, query_type)
                aggregate = aggregates.get(key)
                if aggregate is None:
                    aggregate = ActivityAggregate(
                        device=device,
                        domain=domain,
                        query_type=query_type,
                        first_seen=seen_at,
                        last_seen=seen_at,
                    )
                    aggregates[key] = aggregate
                aggregate.add(
                    seen_at,
                    reason in BLOCKED_REASONS,
                    str(item.get("status") or ""),
                    reason,
                    str(item.get("service_name") or ""),
                )

            if reached_cursor or len(entries) < QUERY_PAGE_SIZE or processed >= max_entries:
                break
            offset += len(entries)

        _save_aggregates(aggregates, unmatched_aggregates, matched_clients)
        if newest_seen:
            config.adguard_last_sync_at = newest_seen
        config.adguard_last_error = ""
        config.save(update_fields=["adguard_last_sync_at", "adguard_last_error", "updated_at"])
        deleted = cleanup_adguard_activity(config.adguard_retention_days)
        return {
            "status": "ok",
            "processed": processed,
            "matched": matched,
            "unmatched": unmatched,
            "invalid": invalid,
            "domains_updated": len(aggregates),
            "deleted": deleted["activity"] + deleted["unmatched_clients"],
            "deleted_activity": deleted["activity"],
            "deleted_unmatched_clients": deleted["unmatched_clients"],
            "unmatched_clients_updated": len(unmatched_aggregates),
            "truncated": processed >= max_entries,
            "last_sync_at": config.adguard_last_sync_at,
        }
    except AdGuardError as exc:
        config.adguard_last_error = stored_error_message("adguard", str(exc))
        config.save(update_fields=["adguard_last_error", "updated_at"])
        raise
