import csv
import io
import ipaddress
import os
import re
import shlex
import stat
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..database_writes import serialized_database_write
from ..datetime_utils import utc_isoformat
from ..models import AppSettings, Device
from ..scanning.identity import guess_device_identity, validated_hostname
from ..scanning.reconciliation import IP_IDENTITY_CONFLICT_MARKER, IP_IDENTITY_CONFLICT_WINDOW


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 50_000
FORMATS = {"dnsmasq", "kea", "isc"}


class DhcpError(RuntimeError):
    pass


def lease_path(filename):
    value = str(filename or "").strip()
    candidate = Path(value)
    if not value or candidate.is_absolute():
        raise DhcpError("Enter a lease filename relative to the DHCP lease directory.")
    try:
        root = Path(settings.DHCP_LEASE_DIRECTORY).resolve()
        path = (root / candidate).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise DhcpError("The DHCP lease path is invalid.") from exc
    if not path.is_relative_to(root) or path == root:
        raise DhcpError("The lease file must be inside the DHCP lease directory.")
    return path


def read_lease_file(filename):
    path = lease_path(filename)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise DhcpError("The lease source must be a regular file.")
            content = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
        if len(content) > MAX_FILE_BYTES:
            raise DhcpError("The DHCP lease file exceeds the 5 MiB limit.")
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise DhcpError("The lease file changed while being read. Try syncing again.")
        modified = datetime.fromtimestamp(before.st_mtime, tz=datetime_timezone.utc)
        if not settings.USE_TZ:
            modified = timezone.make_naive(modified, datetime_timezone.utc)
        return content.decode("utf-8-sig"), min(modified, timezone.now())
    except (OSError, UnicodeError, ValueError) as exc:
        raise DhcpError("The DHCP lease file could not be read as UTF-8. Check its mount and permissions.") from exc


def _epoch(value):
    number = int(value)
    if number < 0:
        raise ValueError("negative timestamp")
    return number


def _dnsmasq_rows(text):
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "duid":
            continue
        if len(parts) != 5:
            raise DhcpError("Invalid dnsmasq lease row. Expected expiry, MAC, IPv4, hostname, and client ID.")
        expires, mac, ip, name, _ = parts
        yield {"ip": ip, "mac": mac, "name": "" if name == "*" else name, "expires": expires, "active": True}


def _kea_rows(text):
    reader = csv.DictReader(io.StringIO(text), strict=True)
    required = {"address", "hwaddr", "valid_lifetime", "expire", "hostname"}
    if not required.issubset(reader.fieldnames or []):
        raise DhcpError("The Kea CSV header must include address, hwaddr, valid_lifetime, expire, and hostname.")
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise DhcpError("The Kea lease file contains an incomplete CSV row.")
        lifetime = _epoch(row["valid_lifetime"])
        expires = _epoch(row["expire"])
        yield {
            "ip": row["address"], "mac": row["hwaddr"], "name": row["hostname"],
            "expires": 0 if lifetime == 0xFFFFFFFF else expires,
            "active": row.get("state", "0") == "0" and lifetime > 0 and (expires > 0 or lifetime == 0xFFFFFFFF),
        }


def _isc_rows(text):
    lexer = shlex.shlex(text, posix=False, punctuation_chars="{};")
    lexer.whitespace_split = True
    tokens = (
        piece for token in lexer
        for piece in (list(token) if token and set(token) <= set("{};") else [token])
    )
    iterator = iter(tokens)
    depth = 0
    for token in iterator:
        if token == "lease" and depth == 0:
            ip = next(iterator)
            if next(iterator) != "{":
                raise ValueError("missing lease block")
            row = {"ip": ip, "mac": "", "name": "", "expires": None, "active": False}
            statement = []
            block_depth = 1
            for token in iterator:
                if token == "{":
                    block_depth += 1
                    statement = []
                elif token == "}":
                    block_depth -= 1
                    statement = []
                    if block_depth == 0:
                        break
                elif block_depth == 1 and token == ";":
                    if statement[:2] == ["hardware", "ethernet"] and len(statement) == 3:
                        row["mac"] = statement[2]
                    elif statement[:2] == ["binding", "state"]:
                        row["active"] = statement[2:] == ["active"]
                    elif statement[:1] == ["client-hostname"] and len(statement) == 2:
                        row["name"] = shlex.split(statement[1])[0]
                    elif statement[:1] == ["ends"]:
                        if statement[1:] == ["never"]:
                            row["expires"] = 0
                        elif statement[1:2] == ["epoch"] and len(statement) == 3:
                            row["expires"] = _epoch(statement[2])
                        else:
                            end = datetime.strptime(" ".join(statement[-2:]), "%Y/%m/%d %H:%M:%S")
                            row["expires"] = end.replace(tzinfo=datetime_timezone.utc).timestamp()
                    statement = []
                elif block_depth == 1:
                    statement.append(token)
            if block_depth:
                raise ValueError("incomplete lease block")
            yield row
        elif token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced blocks")
    if depth:
        raise ValueError("incomplete block")


def parse_leases(text, source_format, now=None):
    if source_format not in FORMATS:
        raise DhcpError("Choose dnsmasq, Kea DHCPv4, or ISC DHCPv4.")
    now = now or timezone.now()
    now_timestamp = (now.replace(tzinfo=datetime_timezone.utc) if timezone.is_naive(now) else now).timestamp()
    latest = {}
    invalid = 0
    try:
        rows = {"dnsmasq": _dnsmasq_rows, "kea": _kea_rows, "isc": _isc_rows}[source_format]
        for index, row in enumerate(rows(text) if text.strip() else []):
            if index >= MAX_RECORDS:
                raise DhcpError("The DHCP lease file exceeds the 50,000 record limit.")
            try:
                ip = ipaddress.ip_address(row["ip"])
            except ValueError:
                invalid += 1
                continue
            if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
                invalid += 1
                continue
            # Journals append updates and tombstones; only the last record per IP counts.
            latest[str(ip)] = row
    except (ValueError, StopIteration, RuntimeError, csv.Error) as exc:
        raise DhcpError("The DHCP lease file is malformed or incomplete. No devices were changed.") from exc
    active = []
    expired = 0
    for ip, row in latest.items():
        mac = str(row["mac"]).lower().replace("-", ":")
        if not row["active"]:
            expired += 1
            continue
        try:
            expires = _epoch(row["expires"])
        except (TypeError, ValueError):
            invalid += 1
            continue
        if expires and expires <= now_timestamp:
            expired += 1
            continue
        if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac) or mac == "00:00:00:00:00:00" or int(mac[:2], 16) & 1:
            invalid += 1
            continue
        active.append({"ip": ip, "mac": mac, "name": validated_hostname(row["name"], mac)})
    return active, {"active_leases": len(active), "expired_leases": expired, "invalid_leases": invalid}


def inspect_lease_source(filename, source_format):
    text, observed_at = read_lease_file(filename)
    leases, summary = parse_leases(text, source_format)
    return leases, summary, observed_at


def _apply_leases(leases, observed_at, create_devices):
    summary = {"devices_discovered": 0, "devices_updated": 0, "devices_skipped": 0, "identity_conflicts": 0}
    by_mac = {}
    for lease in leases:
        by_mac.setdefault(lease["mac"], []).append(lease)
    for mac, records in by_mac.items():
        if len(records) != 1:
            summary["devices_skipped"] += len(records)
            continue
        lease = records[0]
        device = Device.objects.filter(mac=mac).first()
        if device and device.archived:
            summary["devices_skipped"] += 1
            continue
        if device and device.ip != lease["ip"] and (
            device.lastseen > observed_at or device.ip_assignments.filter(valid_from__gt=observed_at).exists()
        ):
            summary["devices_skipped"] += 1
            continue
        competing = Device.objects.filter(ip=lease["ip"], archived=False).exclude(mac=mac).filter(
            Q(lastseen__gte=timezone.now() - IP_IDENTITY_CONFLICT_WINDOW)
            | Q(ip_assignments__ip=lease["ip"], ip_assignments__valid_from__gt=observed_at,
                ip_assignments__valid_until__isnull=True)
        ).distinct()
        if competing.exists():
            macs = sorted({mac, *competing.values_list("mac", flat=True)})[:4]
            reason = f"IP {lease['ip']}{IP_IDENTITY_CONFLICT_MARKER}{', '.join(macs)}"
            ids = [*competing.values_list("pk", flat=True), *([device.pk] if device else [])]
            Device.objects.filter(pk__in=ids).filter(
                Q(identity_conflict_detected_at__isnull=True)
                | Q(identity_conflict_detected_at__lte=observed_at)
            ).update(identity_conflict_reason=reason, identity_conflict_detected_at=observed_at)
            summary["identity_conflicts"] += 1
            continue
        if device is None:
            if not create_devices:
                summary["devices_skipped"] += 1
                continue
            identity = guess_device_identity(hostname=lease["name"], mac=mac)
            device = Device(
                mac=mac, ip=lease["ip"], hostname=lease["name"], name=identity["name"], icon=identity["icon"],
                hostname_source=Device.IdentitySource.DHCP if lease["name"] else "",
                online=False, status=Device.Status.RECENTLY_SEEN, status_source=Device.StatusSource.RECENT,
                status_reason="Observed in DHCP lease source", firstseen=observed_at,
                lastseen=observed_at, last_status_check=observed_at,
            )
            device.save(ip_observed_at=observed_at)
            summary["devices_discovered"] += 1
            continue
        fields = []
        if device.ip != lease["ip"]:
            device.ip = lease["ip"]
            fields.append("ip")
        if not device.known and lease["name"] and device.hostname_source in {
            "", Device.IdentitySource.DHCP, Device.IdentitySource.INFERRED, Device.IdentitySource.IMPORTED,
        } and device.hostname != lease["name"]:
            device.hostname = lease["name"]
            device.hostname_source = Device.IdentitySource.DHCP
            fields.extend(["hostname", "hostname_source"])
            if not device.name or device.name == "Device":
                device.name = guess_device_identity(hostname=lease["name"], mac=mac)["name"]
                fields.append("name")
        if fields:
            device.save(update_fields=fields, ip_observed_at=observed_at)
            summary["devices_updated"] += 1
    return summary


def sync_dhcp(config=None):
    # Share the cross-process SQLite lock with scans and controller integrations.
    with serialized_database_write():
        config = config or AppSettings.load()
        if not config.dhcp_enabled:
            return {"status": "disabled"}
        try:
            source = (config.dhcp_lease_file, config.dhcp_format, config.dhcp_create_devices)
            leases, summary, observed_at = inspect_lease_source(config.dhcp_lease_file, config.dhcp_format)
            with transaction.atomic():
                config.refresh_from_db()
                if not config.dhcp_enabled:
                    return {"status": "disabled"}
                if source != (config.dhcp_lease_file, config.dhcp_format, config.dhcp_create_devices):
                    raise DhcpError("DHCP settings changed during sync. Try again.")
                summary.update(_apply_leases(leases, observed_at, config.dhcp_create_devices))
                summary.update({"status": "ok", "observed_at": utc_isoformat(observed_at)})
                config.dhcp_last_sync_at = timezone.now()
                config.dhcp_last_sync_summary = summary
                config.dhcp_last_error = ""
                config.save(update_fields=["dhcp_last_sync_at", "dhcp_last_sync_summary", "dhcp_last_error", "updated_at"])
            return summary
        except DhcpError as exc:
            config.dhcp_last_error = str(exc)
            config.save(update_fields=["dhcp_last_error", "updated_at"])
            raise
