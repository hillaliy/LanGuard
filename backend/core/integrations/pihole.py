import ipaddress
import logging
import re
from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from django.utils import timezone

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
BLOCKED_STATUSES = {
    "GRAVITY",
    "REGEX",
    "DENYLIST",
    "EXTERNAL_BLOCKED_IP",
    "EXTERNAL_BLOCKED_NULL",
    "EXTERNAL_BLOCKED_NXRA",
    "GRAVITY_CNAME",
    "REGEX_CNAME",
    "DENYLIST_CNAME",
    "SPECIAL_DOMAIN",
    "CACHE_STALE_BLOCKED",
}


class PiHoleError(RuntimeError):
    pass


def normalize_pihole_url(value):
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PiHoleError("Enter a valid Pi-hole HTTP or HTTPS URL.")
    path = parsed.path.rstrip("/")
    if path.endswith("/admin"):
        path = path[:-6]
    if path.endswith("/api"):
        path = path[:-4]
    return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))


class PiHoleClient:
    def __init__(self, base_url, password="", timeout=10):
        self.base_url = normalize_pihole_url(base_url)
        self.api_url = f"{self.base_url}/api"
        self.password = password
        self.timeout = timeout
        self.session_id = ""

    def _request(self, method, path, *, params=None, json=None, authenticated=True):
        headers = {"Accept": "application/json"}
        if authenticated and self.session_id:
            headers["X-FTL-SID"] = self.session_id
        try:
            response = requests.request(
                method,
                f"{self.api_url}/{path.lstrip('/')}",
                params=params,
                json=json,
                timeout=self.timeout,
                headers=headers,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise PiHoleError("Pi-hole did not respond before the timeout.") from exc
        except requests.RequestException as exc:
            response_status = getattr(getattr(exc, "response", None), "status_code", None)
            if response_status in {400, 401, 403}:
                message = "Pi-hole rejected the application password."
            elif response_status == 404:
                message = "Pi-hole v6 API endpoints were not found at this URL."
            elif response_status:
                message = f"Pi-hole returned HTTP {response_status}."
            else:
                message = "LanGuard could not connect to Pi-hole."
            raise PiHoleError(message) from exc

        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise PiHoleError("Pi-hole returned an unreadable response.") from exc

    def authenticate(self):
        if self.password:
            payload = self._request(
                "POST",
                "auth",
                json={"password": self.password},
                authenticated=False,
            )
        else:
            payload = self._request("GET", "auth", authenticated=False)
        session = payload.get("session") if isinstance(payload, dict) else None
        if not isinstance(session, dict) or not session.get("valid"):
            raise PiHoleError("Pi-hole requires a valid application password.")
        self.session_id = str(session.get("sid") or "")
        return session

    def close(self):
        if not self.session_id:
            return
        try:
            self._request("DELETE", "auth")
        except PiHoleError:
            LOGGER.debug("Could not close Pi-hole API session", exc_info=True)
        finally:
            self.session_id = ""

    def version(self):
        return self._request("GET", "info/version")

    def queries(self, *, from_timestamp=None, cursor=None, length=QUERY_PAGE_SIZE):
        params = {"length": length, "disk": "true"}
        if from_timestamp is not None:
            params["from"] = from_timestamp
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "queries", params=params)

    def dhcp_leases(self):
        return self._request("GET", "dhcp/leases")


def parse_query_time(value):
    try:
        parsed = datetime.fromtimestamp(float(value), tz=datetime_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    if not settings.USE_TZ:
        return timezone.make_naive(parsed, datetime_timezone.utc)
    return parsed


def _normalized_mac(value):
    mac = str(value or "").strip().lower().replace("-", ":")
    if not MAC_PATTERN.fullmatch(mac) or mac in {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}:
        return ""
    first_octet = int(mac[:2], 16)
    return "" if first_octet & 1 else mac


def _sync_dhcp_leases(leases, observed_at):
    discovered = 0
    updated = 0
    conflicts = 0
    invalid = 0
    conflict_cutoff = observed_at - IP_IDENTITY_CONFLICT_WINDOW

    for lease in leases:
        if not isinstance(lease, dict):
            invalid += 1
            continue
        mac = _normalized_mac(lease.get("hwaddr"))
        ip = normalize_client_ipv4(lease.get("ip"))
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
        hostname = validated_hostname(lease.get("name"), mac)
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
            identity = guess_device_identity(hostname=hostname, mac=mac)
            device = Device(
                icon=identity["icon"],
                name=identity["name"],
                hostname=hostname,
                hostname_source=Device.IdentitySource.PIHOLE if hostname else "",
                ip=ip,
                mac=mac,
                online=False,
                status=Device.Status.RECENTLY_SEEN,
                status_source=Device.StatusSource.RECENT,
                status_reason="Observed in Pi-hole DHCP leases",
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
            device.hostname_source = Device.IdentitySource.PIHOLE
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
        "identity_conflicts": conflicts,
        "invalid_leases": invalid,
    }


def test_pihole_connection(base_url, password=""):
    client = PiHoleClient(base_url, password)
    try:
        client.authenticate()
        version_payload = client.version()
        query_payload = client.queries(length=1)
        lease_payload = client.dhcp_leases()
        version = version_payload.get("version") if isinstance(version_payload, dict) else None
        if isinstance(version, dict):
            version = version.get("core", {}).get("local", {}).get("version") or version.get("ftl", {}).get("local", {}).get("version")
        return {
            "version": str(version or ""),
            "query_api": isinstance(query_payload.get("queries"), list),
            "active_leases": len(lease_payload.get("leases") or []),
        }
    finally:
        client.close()


def sync_pihole(config=None, max_entries=MAX_SYNC_ENTRIES):
    config = config or AppSettings.load()
    if not config.pihole_enabled:
        return {"status": "disabled", "processed": 0, "matched": 0, "unmatched": 0}
    if not config.pihole_url:
        raise PiHoleError("Configure the Pi-hole URL before syncing.")

    client = PiHoleClient(config.pihole_url, config.pihole_password)
    cursor_time = config.pihole_last_sync_at
    cursor_id = config.pihole_last_query_id
    assignments_by_ip = ip_assignment_index()
    aggregates = {}
    unmatched_aggregates = {}
    processed = matched = unmatched = invalid = 0
    next_cursor = None
    newest_time = cursor_time
    newest_id = cursor_id
    observed_at = timezone.now()

    try:
        client.authenticate()
        lease_payload = client.dhcp_leases()
        leases = lease_payload.get("leases") if isinstance(lease_payload, dict) else None
        if not isinstance(leases, list):
            raise PiHoleError("Pi-hole returned an unreadable DHCP lease response.")
        dhcp_result = _sync_dhcp_leases(leases, observed_at)
        assignments_by_ip = ip_assignment_index()

        while processed < max_entries:
            payload = client.queries(
                from_timestamp=cursor_time.timestamp() if cursor_time else None,
                cursor=next_cursor,
                length=min(QUERY_PAGE_SIZE, max_entries - processed),
            )
            entries = payload.get("queries") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                break
            for item in entries:
                seen_at = parse_query_time(item.get("time"))
                query_id = item.get("id")
                try:
                    query_id = int(query_id)
                except (TypeError, ValueError):
                    query_id = 0
                if seen_at is None:
                    invalid += 1
                    continue
                if cursor_time and (
                    seen_at < cursor_time
                    or (seen_at == cursor_time and cursor_id is not None and query_id <= cursor_id)
                ):
                    continue

                processed += 1
                if newest_time is None or seen_at > newest_time or (
                    seen_at == newest_time and query_id > (newest_id or 0)
                ):
                    newest_time, newest_id = seen_at, query_id
                client_data = item.get("client") if isinstance(item.get("client"), dict) else {}
                client_value = str(client_data.get("ip") or "").strip()
                device = device_for_client_at(client_value, seen_at, assignments_by_ip)
                domain = normalize_domain(item.get("domain"))
                status = str(item.get("status") or "").strip().upper()
                blocked = status in BLOCKED_STATUSES
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
                        aggregate.add(seen_at, domain, blocked, status, status)
                    continue

                matched += 1
                query_type = str(item.get("type") or "").strip().upper()[:16]
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
                aggregate.add(seen_at, blocked, status, status, "")

            next_value = payload.get("cursor")
            if len(entries) < QUERY_PAGE_SIZE or next_value in {None, next_cursor}:
                break
            next_cursor = next_value

        _save_aggregates(
            aggregates,
            unmatched_aggregates,
            assignments_by_ip,
            provider="pihole",
        )
        if newest_time:
            config.pihole_last_sync_at = newest_time
            config.pihole_last_query_id = newest_id
        config.pihole_last_error = ""
        config.save(
            update_fields=[
                "pihole_last_sync_at",
                "pihole_last_query_id",
                "pihole_last_error",
                "updated_at",
            ]
        )
        deleted = cleanup_adguard_activity(
            config.pihole_retention_days,
            provider="pihole",
        )
        return {
            "status": "ok",
            "processed": processed,
            "matched": matched,
            "unmatched": unmatched,
            "invalid": invalid,
            "domains_updated": len(aggregates),
            "unmatched_clients_updated": len(unmatched_aggregates),
            "deleted": deleted["activity"] + deleted["unmatched_clients"],
            "truncated": processed >= max_entries,
            "last_sync_at": config.pihole_last_sync_at,
            **dhcp_result,
        }
    except PiHoleError as exc:
        config.pihole_last_error = stored_error_message("pihole", str(exc))
        config.save(update_fields=["pihole_last_error", "updated_at"])
        raise
    finally:
        client.close()
