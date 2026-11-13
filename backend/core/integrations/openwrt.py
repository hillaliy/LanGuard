"""Read-only OpenWrt inventory via the HTTP ubus endpoint."""

import ipaddress
import json
import re
from collections import Counter, defaultdict
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

import requests
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..database_writes import serialized_database_write
from ..datetime_utils import utc_isoformat
from ..models import AppSettings, Device
from .client_identity import apply_client_observations

MAX_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 5000
MAX_ACCESS_POINTS = 16
EMPTY_SESSION = "0" * 32
READ_METHODS = {
    "leases": ("luci-rpc", "getDHCPLeases"),
    "host_hints": ("luci-rpc", "getHostHints"),
    "wireless": ("luci-rpc", "getWirelessDevices"),
    "associations": ("iwinfo", "assoclist"),
}
IFNAME = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,14}")


class OpenWrtError(RuntimeError):
    pass


class OpenWrtAuthError(OpenWrtError):
    pass


class OpenWrtUnavailable(OpenWrtError):
    pass


def normalize_openwrt_url(value):
    try:
        value = str(value or "").strip()
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/", "/ubus", "/ubus/"}
            or any(char.isspace() or not char.isprintable() or char in "\\?#" for char in value)
            or parsed.port == 0
        ):
            raise ValueError
    except ValueError as exc:
        raise OpenWrtError("Enter the OpenWrt HTTP or HTTPS origin or its /ubus URL, without credentials.") from exc
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), "", "", ""))


def _dict(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    if not isinstance(value, list) or len(value) > MAX_RECORDS:
        raise OpenWrtError("OpenWrt returned an invalid or oversized inventory list.")
    return (_dict(row) for row in value)


def _text(value, limit=255):
    return "".join(c for c in value if c.isprintable()).strip()[:limit] if isinstance(value, str) else ""


def _mac(value):
    mac = value.lower() if isinstance(value, str) else ""
    if re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac) and mac != "00:00:00:00:00:00" and not int(mac[:2], 16) & 1:
        return mac
    return ""


def _address(value, version=4):
    if not isinstance(value, str) or len(value) > 45 or "%" in value:
        return ""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return ""
    if ip.version == version and not (ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_reserved):
        return str(ip)
    return ""


class OpenWrtClient:
    def __init__(self, url, username, password, verify_ssl=True):
        self.url = normalize_openwrt_url(url)
        self.username, self.password = username, password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.trust_env = False
        self.token = EMPTY_SESSION
        self.deadline = monotonic() + 25
        self.request_id = 0

    def _call(self, operation, device=""):
        params = {}
        if operation == "login":
            target = ("session", "login")
            params = {"username": self.username, "password": self.password, "timeout": 60}
        elif operation == "logout":
            target = ("session", "destroy")
        else:
            target = READ_METHODS[operation]
            if operation == "leases":
                params = {"family": 4}
            if operation == "associations":
                if not IFNAME.fullmatch(device):
                    raise OpenWrtError("Invalid wireless interface name.")
                params = {"device": device}
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise OpenWrtError("OpenWrt inventory collection timed out.")
        self.request_id += 1
        try:
            with self.session.post(
                f"{self.url}/ubus",
                json={"jsonrpc": "2.0", "id": self.request_id, "method": "call",
                      "params": [self.token, *target, params]},
                timeout=(min(3, remaining), min(5, remaining)), verify=self.verify_ssl,
                allow_redirects=False, stream=True,
            ) as response:
                if response.status_code in {401, 403, 429}:
                    raise OpenWrtAuthError("OpenWrt rejected the login or HTTP access.")
                if 300 <= response.status_code < 400:
                    raise OpenWrtError("OpenWrt redirected /ubus. Enter the final router origin.")
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if monotonic() > self.deadline:
                        raise OpenWrtError("OpenWrt inventory collection timed out.")
                    if len(body) + len(chunk) > MAX_BYTES:
                        raise OpenWrtError("OpenWrt response exceeds the 2 MiB limit.")
                    body.extend(chunk)
                payload = json.loads(body)
        except requests.exceptions.SSLError:
            raise OpenWrtError("OpenWrt TLS certificate could not be verified.") from None
        except requests.RequestException:
            raise OpenWrtError("OpenWrt /ubus did not respond successfully. Check HTTP ubus access and the router URL.") from None
        except (ValueError, RecursionError):
            raise OpenWrtError("OpenWrt /ubus did not return valid JSON.") from None
        if not isinstance(payload, dict) or payload.get("id") != self.request_id or payload.get("jsonrpc") != "2.0":
            raise OpenWrtError("OpenWrt returned an invalid JSON-RPC response.")
        code = _dict(payload.get("error")).get("code")
        result = payload.get("result")
        status = result[0] if isinstance(result, list) and result else None
        if code == -32001 or (operation == "login" and (code == -32002 or status == 6)):
            raise OpenWrtAuthError("OpenWrt rejected the login or session. Check rpcd credentials.")
        if code in (-32601, -32000, -32002) or status in (3, 4, 6, 8):
            raise OpenWrtUnavailable("OpenWrt RPC method is unavailable or not allowed by the account.")
        if code is not None or type(status) is not int or status != 0 or len(result) > 2:
            raise OpenWrtError("OpenWrt returned an unsuccessful RPC result.")
        if len(result) == 2 and not isinstance(result[1], dict):
            raise OpenWrtError("OpenWrt returned an invalid RPC result.")
        return result[1] if len(result) == 2 else {}

    def read(self, operation, unavailable, device=""):
        try:
            return self._call(operation, device)
        except OpenWrtUnavailable:
            label = f"{operation} ({device})" if device else operation
            unavailable.append(label)
            return None

    def login(self):
        if not self.username or not self.password:
            raise OpenWrtAuthError("Enter OpenWrt rpcd credentials.")
        token = self._call("login").get("ubus_rpc_session")
        if not isinstance(token, str) or token == EMPTY_SESSION or not re.fullmatch(r"[0-9a-fA-F]{32}", token):
            raise OpenWrtAuthError("OpenWrt did not issue a valid session.")
        self.token = token

    def close(self):
        try:
            if self.token != EMPTY_SESSION:
                self._call("logout")
        except OpenWrtError:
            pass
        finally:
            self.token = EMPTY_SESSION
            self.session.close()


def _lease_clients(payload):
    clients = defaultdict(dict)
    for row in _rows(payload.get("dhcp_leases")):
        mac, ip = _mac(row.get("macaddr")), _address(row.get("ipaddr"))
        expires = row.get("expires")
        # LuCI represents an unlimited lease as boolean false, not numeric zero.
        if mac and ip and (expires is False or (type(expires) is int and expires > 0)):
            clients[mac][ip] = {"mac": mac, "ip": ip, "name": _text(row.get("hostname")),
                                "lease_interface": _text(row.get("interface"), 64)}
    counts = Counter(ip for ips in clients.values() for ip in ips)
    return [row for ips in clients.values() if len(ips) == 1
            for ip, row in ips.items() if counts[ip] == 1]


def _wireless_observations(client, payload, unavailable):
    observations, interfaces = defaultdict(dict), set()
    for radio, radio_data in payload.items():
        for interface in _rows(_dict(radio_data).get("interfaces", [])):
            name = interface.get("ifname")
            config = _dict(interface.get("config"))
            if (not isinstance(name, str) or not IFNAME.fullmatch(name)
                    or config.get("mode") != "ap" or name in interfaces):
                continue
            if len(interfaces) >= MAX_ACCESS_POINTS:
                unavailable.append("additional access points (limit reached)")
                return observations
            interfaces.add(name)
            stations = client.read("associations", unavailable, name)
            if stations is None:
                continue
            info = _dict(interface.get("iwinfo"))
            networks = config.get("network")
            if isinstance(networks, str):
                networks = networks.split()
            context = {"interface": name, "radio": _text(radio, 64),
                       "ssid": _text(info.get("ssid") or config.get("ssid"), 64),
                       "networks": [_text(v, 64) for v in networks[:8] if _text(v, 64)]
                       if isinstance(networks, list) else []}
            for key in ("channel", "frequency"):
                value = info.get(key, _dict(_dict(radio_data).get("iwinfo")).get(key))
                if type(value) is int and 0 < value <= 100000:
                    context[key] = value
            for station in _rows(stations.get("results")):
                mac = _mac(station.get("mac"))
                if not mac:
                    continue
                signal = station.get("signal")
                if type(signal) is int and 2**32 - 127 <= signal < 2**32:
                    signal -= 2**32
                rssi = signal if type(signal) is int and -127 <= signal < 0 else None
                observations[mac][name] = {**context, "rssi": rssi}
                if len(observations) > MAX_RECORDS:
                    raise OpenWrtError("OpenWrt returned too many wireless clients.")
    return observations


def inspect_openwrt(url, username, password, verify_ssl=True):
    client = OpenWrtClient(url, username, password, verify_ssl)
    unavailable = []
    try:
        client.login()
        lease_data = client.read("leases", unavailable)
        hints = client.read("host_hints", unavailable)
        wireless_data = client.read("wireless", unavailable)
        if lease_data is None and hints is None and wireless_data is None:
            raise OpenWrtError("No supported inventory RPC methods are available. Check LuCI packages and rpcd read permissions.")
        leases = _lease_clients(lease_data) if lease_data is not None else []
        if len(hints or {}) > MAX_RECORDS:
            raise OpenWrtError("OpenWrt returned too many host hints.")
        wireless = _wireless_observations(client, wireless_data or {}, unavailable)
        observations = {row["mac"]: {"lease_ip": row["ip"], "lease_interface": row["lease_interface"],
                                     "name": row["name"]} for row in leases}
        hint_count = 0
        for key, hint in (hints or {}).items():
            mac = _mac(key)
            if not mac or not isinstance(hint, dict):
                continue
            addresses = set()
            for field, version in (("ipaddrs", 4), ("ip6addrs", 6)):
                values = hint.get(field)
                if isinstance(values, list):
                    addresses.update(filter(None, (_address(value, version) for value in values[:16])))
            if addresses:
                entry = observations.setdefault(mac, {})
                entry["hint_addresses"] = sorted(addresses)
                entry["name"] = entry.get("name") or _text(hint.get("name"))
                hint_count += 1
        for mac, associations in wireless.items():
            observations.setdefault(mac, {})["wireless"] = list(associations.values())
        return leases, observations, {"leases": len(leases), "host_hints": hint_count,
                                      "wireless_clients": len(wireless), "unavailable": unavailable}
    finally:
        client.close()


def _source(config):
    return (config.openwrt_url, config.openwrt_username, config.openwrt_password,
            config.openwrt_verify_ssl, config.openwrt_create_devices)


def sync_openwrt(*, manual=False):
    config = AppSettings.load()
    if not config.openwrt_enabled:
        return {"status": "disabled"}
    if config.openwrt_auth_failed and not manual:
        return {"status": "auth_paused"}
    source = _source(config)
    observed_at = timezone.now()
    try:
        leases, observations, summary = inspect_openwrt(*source[:4])
    except OpenWrtError as exc:
        with serialized_database_write(timeout=2):
            AppSettings.objects.filter(
                pk=config.pk, openwrt_enabled=True, openwrt_url=source[0],
                openwrt_username=source[1], openwrt_password=source[2], openwrt_verify_ssl=source[3],
            ).filter(Q(openwrt_last_sync_at__isnull=True) | Q(openwrt_last_sync_at__lte=observed_at)).update(
                openwrt_last_error=str(exc), openwrt_auth_failed=isinstance(exc, OpenWrtAuthError),
            )
        raise

    with serialized_database_write(timeout=2), transaction.atomic():
        config.refresh_from_db()
        if not config.openwrt_enabled:
            return {"status": "disabled"}
        if source != _source(config) or (config.openwrt_last_sync_at and config.openwrt_last_sync_at > observed_at):
            raise OpenWrtError("OpenWrt settings or observations changed during sync. Try again.")
        devices = Device.objects.in_bulk(observations, field_name="mac")
        # Router lease files and host hints are not authoritative over scanner IP ownership.
        new_leases = [row for row in leases if row["mac"] not in devices]
        summary.update(apply_client_observations(
            new_leases, observed_at, config.openwrt_create_devices,
            identity_source=Device.IdentitySource.OPENWRT,
            observation_reason="Reported by an OpenWrt DHCP lease; not verified by a LanGuard scan",
        ))
        stamp = utc_isoformat(observed_at)
        changed = []
        for device in Device.objects.filter(mac__in=observations, archived=False):
            data = observations[device.mac]
            if device.identity_conflict_reason:
                continue
            if data.get("lease_ip") != device.ip:
                data = {key: value for key, value in data.items() if key not in {"lease_ip", "lease_interface"}}
            if not any(data.get(key) for key in ("lease_ip", "hint_addresses", "wireless")):
                continue
            device.openwrt_data = {**data, "observed_at": stamp, "router_url": config.openwrt_url}
            changed.append(device)
        Device.objects.bulk_update(changed, ["openwrt_data"])
        summary.update(status="ok", observed_at=stamp, clients_enriched=len(changed))
        config.openwrt_last_sync_at = observed_at
        config.openwrt_last_sync_summary = summary
        config.openwrt_last_error = ""
        config.openwrt_auth_failed = False
        config.save(update_fields=["openwrt_last_sync_at", "openwrt_last_sync_summary",
                                   "openwrt_last_error", "openwrt_auth_failed", "updated_at"])
    return summary
