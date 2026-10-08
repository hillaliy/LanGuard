import ipaddress
import logging
import re
from datetime import timezone as datetime_timezone
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .adguard import (
    ActivityAggregate,
    UnmatchedClientAggregate,
    _save_aggregates,
    cleanup_adguard_activity,
    device_for_client_at,
    ip_assignment_index,
    normalize_client_ipv4,
    normalize_domain,
)
from ..models import AppSettings, Device
from ..scanning.identity import guess_device_identity, validated_hostname
from ..scanning.reconciliation import (
    IP_IDENTITY_CONFLICT_MARKER,
    IP_IDENTITY_CONFLICT_WINDOW,
)
from ..user_messages import stored_error_message


LOGGER = logging.getLogger(__name__)
QUERY_PAGE_SIZE = 500
MAX_SYNC_ENTRIES = 5000
MAC_PATTERN = re.compile(r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")
BLOCKED_RESPONSE_TYPES = {
    "blocked",
    "upstreamblocked",
    "upstreamblockedcached",
    "dropped",
}


class TechnitiumError(RuntimeError):
    pass


def normalize_technitium_url(value):
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise TechnitiumError(
            "Enter a Technitium HTTP or HTTPS base URL without credentials, "
            "query, or fragment."
        )
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4]
    return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))


class TechnitiumClient:
    def __init__(self, base_url, api_token, timeout=10):
        self.base_url = normalize_technitium_url(base_url)
        self.api_url = f"{self.base_url}/api"
        self.api_token = str(api_token or "").strip()
        self.timeout = timeout

    def _get(self, path, params=None):
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }
        try:
            response = requests.get(
                f"{self.api_url}/{path.lstrip('/')}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise TechnitiumError(
                "Technitium DNS Server did not respond before the timeout."
            ) from exc
        except requests.RequestException as exc:
            response_status = getattr(getattr(exc, "response", None), "status_code", None)
            if response_status in {401, 403}:
                message = "Technitium rejected the API token or its permissions."
            elif response_status == 404:
                message = "Technitium v15 API endpoints were not found at this URL."
            elif response_status:
                message = f"Technitium returned HTTP {response_status}."
            else:
                message = "LanGuard could not connect to Technitium DNS Server."
            raise TechnitiumError(message) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TechnitiumError("Technitium returned an unreadable response.") from exc
        if not isinstance(payload, dict):
            raise TechnitiumError("Technitium returned an unreadable response.")
        response_status = str(payload.get("status") or "").lower()
        if response_status == "invalid-token":
            raise TechnitiumError("Technitium rejected the API token.")
        if response_status != "ok":
            error_text = str(payload.get("errorMessage") or "").lower()
            if "access was denied" in error_text:
                message = "The Technitium API token does not have the required view permissions."
            elif "dns application" in error_text:
                message = "The configured Technitium Query Logs app is unavailable."
            else:
                message = "Technitium rejected the API request."
            raise TechnitiumError(message)
        result = payload.get("response")
        if not isinstance(result, dict):
            raise TechnitiumError("Technitium returned an unreadable response.")
        return result

    def apps(self):
        return self._get("apps/list")

    def query_logs(
        self,
        provider,
        *,
        page_number=1,
        entries_per_page=QUERY_PAGE_SIZE,
        start=None,
        end=None,
    ):
        params = {
            "name": provider["name"],
            "classPath": provider["class_path"],
            "pageNumber": page_number,
            "entriesPerPage": entries_per_page,
            "descendingOrder": "false",
        }
        if start is not None:
            params["start"] = _iso_timestamp(start)
        if end is not None:
            params["end"] = _iso_timestamp(end)
        return self._get("logs/query", params=params)

    def dhcp_leases(self):
        return self._get("dhcp/leases/list")


def _iso_timestamp(value):
    if timezone.is_naive(value):
        value = timezone.make_aware(value, datetime_timezone.utc)
    return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")


def parse_technitium_time(value):
    parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    parsed = parsed.astimezone(datetime_timezone.utc)
    if not settings.USE_TZ:
        return timezone.make_naive(parsed, datetime_timezone.utc)
    return parsed


def find_query_log_provider(payload):
    apps = payload.get("apps") if isinstance(payload, dict) else None
    providers = []
    for app in apps if isinstance(apps, list) else []:
        if not isinstance(app, dict):
            continue
        app_name = str(app.get("name") or "").strip()
        dns_apps = app.get("dnsApps")
        for dns_app in dns_apps if isinstance(dns_apps, list) else []:
            if not isinstance(dns_app, dict) or not dns_app.get("isQueryLogs"):
                continue
            class_path = str(dns_app.get("classPath") or "").strip()
            if app_name and class_path:
                providers.append({"name": app_name, "class_path": class_path})
    if not providers:
        raise TechnitiumError(
            "Install and enable a Technitium Query Logs app before syncing DNS activity."
        )
    return sorted(providers, key=lambda item: (item["name"], item["class_path"]))[0]


def normalize_technitium_mac(value):
    mac = str(value or "").strip().lower().replace("-", ":")
    if not MAC_PATTERN.fullmatch(mac) or mac in {
        "00:00:00:00:00:00",
        "ff:ff:ff:ff:ff:ff",
    }:
        return ""
    return "" if int(mac[:2], 16) & 1 else mac


def _sync_dhcp_leases(leases, observed_at, *, create_devices=False):
    discovered = updated = conflicts = invalid = skipped = expired = 0
    conflict_cutoff = observed_at - IP_IDENTITY_CONFLICT_WINDOW

    for lease in leases:
        if not isinstance(lease, dict):
            invalid += 1
            continue
        mac = normalize_technitium_mac(lease.get("hardwareAddress"))
        ip = normalize_client_ipv4(lease.get("address"))
        if not mac or not ip:
            invalid += 1
            continue
        try:
            if not ipaddress.ip_address(ip).is_private:
                invalid += 1
                continue
        except ValueError:
            invalid += 1
            continue
        lease_type = str(lease.get("type") or "").strip().lower()
        lease_expires = parse_technitium_time(lease.get("leaseExpires"))
        if lease_type == "dynamic" and lease_expires and lease_expires <= observed_at:
            expired += 1
            continue

        hostname = validated_hostname(lease.get("hostName"), mac)
        competing = list(
            Device.objects.filter(ip=ip, archived=False, lastseen__gte=conflict_cutoff)
            .exclude(mac=mac)
        )
        conflict_reason = ""
        if competing:
            displayed_macs = ", ".join(sorted({mac, *(item.mac for item in competing)})[:4])
            conflict_reason = f"IP {ip}{IP_IDENTITY_CONFLICT_MARKER}{displayed_macs}"
            Device.objects.filter(pk__in=[item.pk for item in competing]).update(
                identity_conflict_reason=conflict_reason,
                identity_conflict_detected_at=observed_at,
            )
            conflicts += 1

        device = Device.objects.filter(mac=mac).first()
        if device is None:
            if not create_devices:
                skipped += 1
                continue
            identity = guess_device_identity(hostname=hostname, mac=mac)
            device = Device(
                icon=identity["icon"],
                name=identity["name"],
                hostname=hostname,
                hostname_source=Device.IdentitySource.TECHNITIUM if hostname else "",
                ip=ip,
                mac=mac,
                online=False,
                status=Device.Status.RECENTLY_SEEN,
                status_source=Device.StatusSource.RECENT,
                status_reason="Observed in Technitium DHCP leases",
                lastseen=observed_at,
                last_status_check=observed_at,
                identity_conflict_reason=conflict_reason,
                identity_conflict_detected_at=observed_at if conflict_reason else None,
            )
            device.save(
                ip_observed_at=observed_at,
                close_competing_ip_assignments=not conflict_reason,
            )
            discovered += 1
            continue

        update_fields = []
        if device.ip != ip:
            device.ip = ip
            update_fields.append("ip")
        if not device.known and hostname and device.hostname != hostname:
            device.hostname = hostname
            device.hostname_source = Device.IdentitySource.TECHNITIUM
            update_fields.extend(["hostname", "hostname_source"])
        if not device.known and hostname and (not device.name or device.name == "Device"):
            device.name = guess_device_identity(hostname=hostname, mac=mac)["name"]
            update_fields.append("name")
        if conflict_reason:
            device.identity_conflict_reason = conflict_reason
            device.identity_conflict_detected_at = observed_at
            update_fields.extend(["identity_conflict_reason", "identity_conflict_detected_at"])
        if update_fields:
            device.save(
                update_fields=list(dict.fromkeys(update_fields)),
                ip_observed_at=observed_at,
                close_competing_ip_assignments=not conflict_reason,
            )
            updated += 1

    return {
        "leases": len(leases),
        "devices_discovered": discovered,
        "devices_updated": updated,
        "devices_skipped": skipped,
        "identity_conflicts": conflicts,
        "invalid_leases": invalid,
        "expired_leases": expired,
    }


def test_technitium_connection(base_url, api_token, *, dhcp_enabled=False):
    client = TechnitiumClient(base_url, api_token)
    provider = find_query_log_provider(client.apps())
    query_payload = client.query_logs(provider, entries_per_page=1)
    entries = query_payload.get("entries")
    if not isinstance(entries, list):
        raise TechnitiumError("Technitium returned an unreadable query log response.")
    result = {
        "query_log_app": provider["name"],
        "query_log_class": provider["class_path"],
        "query_log_entries": int(query_payload.get("totalEntries") or 0),
        "dhcp_available": False,
        "active_leases": 0,
    }
    if dhcp_enabled:
        lease_payload = client.dhcp_leases()
        leases = lease_payload.get("leases")
        if not isinstance(leases, list):
            raise TechnitiumError("Technitium returned an unreadable DHCP lease response.")
        result.update({"dhcp_available": True, "active_leases": len(leases)})
    return result


def sync_technitium(config=None, max_entries=MAX_SYNC_ENTRIES):
    config = config or AppSettings.load()
    if not config.technitium_enabled:
        return {"status": "disabled", "processed": 0, "matched": 0, "unmatched": 0}
    if not config.technitium_url or not config.technitium_api_token:
        raise TechnitiumError("Configure the Technitium URL and API token before syncing.")

    client = TechnitiumClient(config.technitium_url, config.technitium_api_token)
    cursor_time = config.technitium_last_query_at
    cursor_row = config.technitium_last_query_row
    observed_at = timezone.now()
    assignments_by_ip = ip_assignment_index()
    aggregates = {}
    unmatched_aggregates = {}
    processed = matched = unmatched = invalid = 0
    newest_time = cursor_time
    newest_row = cursor_row
    dhcp_result = {
        "leases": 0,
        "devices_discovered": 0,
        "devices_updated": 0,
        "devices_skipped": 0,
        "identity_conflicts": 0,
        "invalid_leases": 0,
        "expired_leases": 0,
    }

    try:
        provider = find_query_log_provider(client.apps())
        if config.technitium_dhcp_enabled:
            lease_payload = client.dhcp_leases()
            leases = lease_payload.get("leases")
            if not isinstance(leases, list):
                raise TechnitiumError("Technitium returned an unreadable DHCP lease response.")
            dhcp_result = _sync_dhcp_leases(
                leases,
                observed_at,
                create_devices=config.technitium_dhcp_create_devices,
            )
            assignments_by_ip = ip_assignment_index()

        page_number = 1
        total_pages = 1
        while page_number <= total_pages and processed < max_entries:
            payload = client.query_logs(
                provider,
                page_number=page_number,
                entries_per_page=QUERY_PAGE_SIZE,
                start=cursor_time,
                end=observed_at,
            )
            entries = payload.get("entries")
            if not isinstance(entries, list):
                raise TechnitiumError("Technitium returned an unreadable query log response.")
            try:
                total_pages = max(1, int(payload.get("totalPages") or 1))
            except (TypeError, ValueError):
                total_pages = 1
            if not entries:
                break

            for item in entries:
                if processed >= max_entries:
                    break
                if not isinstance(item, dict):
                    invalid += 1
                    processed += 1
                    continue
                seen_at = parse_technitium_time(item.get("timestamp"))
                try:
                    row_number = int(item.get("rowNumber"))
                except (TypeError, ValueError):
                    row_number = 0
                if seen_at is None:
                    invalid += 1
                    processed += 1
                    continue
                if cursor_time and (
                    seen_at < cursor_time
                    or (
                        seen_at == cursor_time
                        and cursor_row is not None
                        and row_number <= cursor_row
                    )
                ):
                    continue

                processed += 1
                if newest_time is None or seen_at > newest_time or (
                    seen_at == newest_time and row_number > (newest_row or 0)
                ):
                    newest_time, newest_row = seen_at, row_number

                client_value = str(item.get("clientIpAddress") or "").strip()
                device = device_for_client_at(client_value, seen_at, assignments_by_ip)
                domain = normalize_domain(item.get("qname"))
                response_type = str(item.get("responseType") or "").strip()
                rcode = str(item.get("rcode") or "").strip()
                blocked = response_type.lower() in BLOCKED_RESPONSE_TYPES
                if device is None or not domain:
                    unmatched += 1
                    if device is None and client_value and domain:
                        aggregate = unmatched_aggregates.get(client_value)
                        if aggregate is None:
                            aggregate = UnmatchedClientAggregate(
                                client=client_value[:255],
                                first_seen=seen_at,
                                last_seen=seen_at,
                            )
                            unmatched_aggregates[client_value] = aggregate
                        aggregate.add(seen_at, domain, blocked, response_type, rcode)
                    continue

                matched += 1
                query_type = str(item.get("qtype") or "").strip().upper()[:16]
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
                aggregate.add(seen_at, blocked, response_type, rcode, "")
            page_number += 1

        _save_aggregates(
            aggregates,
            unmatched_aggregates,
            assignments_by_ip,
            provider="technitium",
        )
        deleted = cleanup_adguard_activity(
            config.technitium_retention_days,
            provider="technitium",
        )
        result = {
            "status": "ok",
            "processed": processed,
            "matched": matched,
            "unmatched": unmatched,
            "invalid": invalid,
            "domains_updated": len(aggregates),
            "unmatched_clients_updated": len(unmatched_aggregates),
            "deleted": deleted["activity"] + deleted["unmatched_clients"],
            "truncated": processed >= max_entries,
            "query_log_app": provider["name"],
            **dhcp_result,
        }
        if newest_time is not None:
            config.technitium_last_query_at = newest_time
            config.technitium_last_query_row = newest_row
        config.technitium_last_sync_at = observed_at
        config.technitium_last_sync_summary = result
        config.technitium_last_error = ""
        config.save(
            update_fields=[
                "technitium_last_query_at",
                "technitium_last_query_row",
                "technitium_last_sync_at",
                "technitium_last_sync_summary",
                "technitium_last_error",
                "updated_at",
            ]
        )
        result["last_sync_at"] = config.technitium_last_sync_at
        return result
    except TechnitiumError as exc:
        config.technitium_last_error = stored_error_message("technitium", str(exc))
        config.save(update_fields=["technitium_last_error", "updated_at"])
        raise
