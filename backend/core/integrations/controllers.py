"""Built-in providers and shared controller synchronization."""

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Protocol

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..database_writes import DatabaseWriteBusy, serialized_database_write
from ..models import ControllerConnection, ControllerDeviceLink, Device
from ..scanning.identity import guess_device_identity, is_default_device_name, validated_hostname
from ..scanning.presence import set_device_status
from .client_identity import flag_competing_ip
from .unifi import ControllerError, UniFiProvider


class InventoryProvider(Protocol):
    def test_connection(self, site_id=None) -> dict: ...
    def list_sites(self) -> list: ...
    def sync_devices(self, site_id) -> tuple[list, int]: ...


PROVIDERS = {ControllerConnection.Provider.UNIFI: UniFiProvider}
SYNC_LEASE = timedelta(minutes=2)


class ControllerBusy(ControllerError):
    pass


def is_due(connection, now):
    return (not connection.last_attempt_at
            or connection.last_attempt_at + timedelta(minutes=connection.sync_interval) <= now)


def _source(connection):
    return connection.url, connection.api_key, connection.verify_ssl, connection.site_id


def reconcile_clients(connection, clients, observed_at):
    source = Device.IdentitySource(connection.provider)
    presence_source = Device.StatusSource(connection.provider)
    counts = dict(created=0, updated=0, skipped=0, conflicts=0)
    by_mac = defaultdict(list)
    for row in clients:
        by_mac[row["mac"]].append(row)
    ips = Counter(ip for rows in by_mac.values() for ip in {row["ip"] for row in rows if row["ip"]})
    external_ids = Counter(row["external_id"] for row in clients)
    for mac, rows in by_mac.items():
        if len(rows) != 1 or external_ids[rows[0]["external_id"]] != 1:
            counts["skipped"] += len(rows)
            continue
        row = rows[0]
        ip = row["ip"]
        device = Device.objects.select_related("merged_into").filter(mac__iexact=mac).order_by("pk").first()
        if device and (
            device.archived or (device.merged_into and device.merged_into.archived)
            or device.lastseen > observed_at
            or (device.last_status_check and device.last_status_check > observed_at)
            or (ip and device.ip != ip and device.ip_assignments.filter(valid_from__gt=observed_at).exists())
        ):
            counts["skipped"] += 1
            continue
        if not device and not ip:
            counts["skipped"] += 1
            continue
        if ip:
            conflict = flag_competing_ip(mac, ip, observed_at, device)
            if conflict or ips[ip] > 1:
                counts["conflicts"] += 1
                continue
        created = device is None
        if created:
            device = Device(mac=mac, ip=ip, known=False, firstseen=observed_at)
        fields = ["online", "lastseen", "missed_scans", "status", "status_source", "status_reason", "last_status_check"]
        if ip and device.ip != ip:
            device.ip = ip
            fields.append("ip")
        if not device.known:
            hostname = validated_hostname(row["hostname"], mac)
            if hostname and device.hostname_source in ("", source, Device.IdentitySource.INFERRED):
                device.hostname, device.hostname_source = hostname, source
                fields.extend(["hostname", "hostname_source"])
            if row["vendor"] and device.vendor_source in ("", source, Device.IdentitySource.INFERRED):
                device.vendor, device.vendor_source = row["vendor"], source
                fields.extend(["vendor", "vendor_source"])
            identity = guess_device_identity(device.hostname, device.vendor, mac)
            if is_default_device_name(device.name):
                device.name = (row["metadata"].get("name") or identity["name"])[:100]
                fields.append("name")
            if device.icon in ("", "plus", "unknown"):
                device.icon = identity["icon"]
                fields.append("icon")
        device.online, device.lastseen, device.missed_scans = True, observed_at, 0
        set_device_status(device, Device.Status.ONLINE, presence_source, now=observed_at)
        device.save(update_fields=None if created else fields, ip_observed_at=observed_at)
        ControllerDeviceLink.objects.update_or_create(connection=connection, device=device, defaults={
            "external_id": row["external_id"], "metadata": row["metadata"],
            "observed_at": observed_at, "synced_at": timezone.now(),
        })
        counts["created" if created else "updated"] += 1
    return counts


def sync_connection(provider, *, manual=False):
    now = timezone.now()
    lock = now + SYNC_LEASE
    with serialized_database_write(timeout=2), transaction.atomic():
        connection = ControllerConnection.objects.select_for_update().filter(provider=provider, enabled=True).first()
        if not connection:
            return {"status": "disabled"}
        if connection.lock_until and connection.lock_until > now:
            raise ControllerBusy("This controller is already syncing.")
        if not manual and not is_due(connection, now):
            return {"status": "not_due"}
        claimed = ControllerConnection.objects.filter(pk=connection.pk).filter(
            Q(lock_until__isnull=True) | Q(lock_until__lte=now)
        ).update(lock_until=lock, last_attempt_at=now)
        if not claimed:
            raise ControllerBusy("This controller is already syncing.")
    active = ControllerConnection.objects.filter(pk=connection.pk, lock_until=lock)
    try:
        with PROVIDERS[provider](*_source(connection)[:3]) as client:
            clients, total = client.sync_devices(connection.site_id)
        with serialized_database_write(timeout=5), transaction.atomic():
            current = active.select_for_update().first()
            if not current or lock <= timezone.now() or not current.enabled or _source(current) != _source(connection):
                raise ControllerError("Controller settings changed or the synchronization lease expired.")
            counts = reconcile_clients(current, clients, now)
            counts["skipped"] += total - len(clients)
            result = {"status": "ok", "clients_reported": total, **counts}
            if clients:
                result["site_name"] = clients[0]["metadata"].get("site_name", "")
            active.update(last_sync_at=timezone.now(), last_result=result, last_error="", lock_until=None)
            return result
    except ControllerError as exc:
        _release_sync(active, last_error=str(exc))
        raise
    except Exception:
        _release_sync(active, last_error="Could not save UniFi observations.")
        raise


def _release_sync(active, **fields):
    try:
        with serialized_database_write(timeout=2):
            active.update(lock_until=None, **fields)
    except DatabaseWriteBusy:
        # Another process holds the write lock. The short lease will expire.
        pass


def sync_due_connections():
    for provider in ControllerConnection.objects.filter(enabled=True).values_list("provider", flat=True):
        if provider not in PROVIDERS:
            continue
        try:
            sync_connection(provider)
        except ControllerError:
            # The connection records a sanitized result; never log upstream exceptions.
            continue
