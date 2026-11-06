"""Read-only ASUSWRT HTTP client discovery; no shell or configuration hooks."""

import base64
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlunsplit

import requests
from django.db import transaction
from django.utils import timezone

from ..database_writes import serialized_database_write
from ..datetime_utils import utc_isoformat
from ..models import AppSettings, Device
from .client_identity import apply_client_observations

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_CLIENTS = 5000
CLIENT_HOOK = "get_clientlist();nvram_get(productid);nvram_get(firmver);nvram_get(buildno);nvram_get(extendno)"
USER_AGENT = "asusrouter-Android-DUTUtil-1.0.0.3.58-163"


class AsuswrtError(RuntimeError):
    pass


class AsuswrtAuthError(AsuswrtError):
    pass


def normalize_asuswrt_url(value):
    try:
        parsed = urlsplit(str(value or "").strip())
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError("invalid router URL")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("invalid port")
    except ValueError as exc:
        raise AsuswrtError("Enter the router HTTP or HTTPS base URL without credentials, paths, or query parameters.") from exc
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), "", "", ""))


def _text(value, limit=255):
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value.strip() if char.isprintable())[:limit]


class AsuswrtClient:
    def __init__(self, url, username, password, verify_ssl=True):
        self.url = normalize_asuswrt_url(url)
        self.username, self.password = username, password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.trust_env = False
        self.token = ""

    def _request(self, endpoint, data=None, *, expect_json=True):
        # Fixed endpoints and fixed hooks only; never accept caller-supplied router commands.
        if endpoint not in {"login.cgi", "appGet.cgi", "Logout.asp"}:
            raise AsuswrtError("Unsupported ASUSWRT endpoint.")
        if endpoint == "appGet.cgi" and data != {"hook": CLIENT_HOOK}:
            raise AsuswrtError("Unsupported ASUSWRT read hook.")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Cookie"] = f"asus_token={self.token}"
        try:
            with self.session.post(
                f"{self.url}/{endpoint}", data=data, headers=headers, timeout=(5, 15),
                verify=self.verify_ssl, allow_redirects=False, stream=True,
            ) as response:
                if response.status_code in {401, 403, 429}:
                    raise AsuswrtAuthError("ASUSWRT rejected the login or session. Check credentials and router login restrictions.")
                if 300 <= response.status_code < 400:
                    raise AsuswrtError("ASUSWRT redirected the request. Enter the correct HTTP or HTTPS base URL.")
                response.raise_for_status()
                if not expect_json:
                    return {}
                chunks, length = [], 0
                for chunk in response.iter_content(chunk_size=65536):
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        raise AsuswrtError("ASUSWRT response exceeds the 5 MiB limit.")
                    chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
        except requests.exceptions.SSLError as exc:
            raise AsuswrtError("ASUSWRT TLS certificate could not be verified. Trust the router certificate or explicitly disable verification on a trusted LAN.") from exc
        except requests.Timeout as exc:
            raise AsuswrtError("ASUSWRT did not respond before the timeout.") from exc
        except requests.RequestException as exc:
            raise AsuswrtError("ASUSWRT could not be reached or returned an HTTP error. Check its URL and local API access.") from exc
        except (ValueError, UnicodeError) as exc:
            raise AsuswrtError("ASUSWRT did not return JSON. This firmware or endpoint may be unsupported.") from exc
        if not isinstance(payload, dict):
            raise AsuswrtError("ASUSWRT returned an unsupported response structure.")
        if str(payload.get("error_status", "0")) != "0":
            raise AsuswrtAuthError("ASUSWRT refused access. Check credentials, CAPTCHA, and temporary login lockout; automatic login retries are paused.")
        return payload

    def fetch_clients(self):
        if not self.username or not self.password:
            raise AsuswrtAuthError("Enter the ASUSWRT router username and password.")
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode("ascii")
        login = self._request("login.cgi", {"login_authorization": credentials})
        token = login.get("asus_token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", token):
            raise AsuswrtAuthError("ASUSWRT did not issue a login token. Check credentials or firmware API support.")
        self.token = token
        return self._request("appGet.cgi", {"hook": CLIENT_HOOK})

    def close(self):
        try:
            if self.token:
                self._request("Logout.asp", expect_json=False)
        except AsuswrtError:
            pass
        finally:
            self.token = ""
            self.session.close()


def parse_clients(payload):
    entries = payload.get("get_clientlist")
    if not isinstance(entries, dict):
        raise AsuswrtError("The firmware did not return get_clientlist data. No devices were changed.")
    if len(entries) > MAX_CLIENTS + 2:
        raise AsuswrtError("ASUSWRT client list exceeds the 5,000 client limit.")
    clients = []
    summary = {"clients_reported": 0, "clients_inactive": 0, "clients_invalid": 0}
    for key, entry in entries.items():
        if key in {"maclist", "ClientAPILevel"}:
            continue
        summary["clients_reported"] += 1
        if not isinstance(entry, dict):
            summary["clients_invalid"] += 1
            continue
        mac = _text(key).lower().replace("-", ":")
        if (not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac)
                or mac == "00:00:00:00:00:00" or int(mac[:2], 16) & 1
                or (_text(entry.get("mac")) and _text(entry["mac"]).lower().replace("-", ":") != mac)):
            summary["clients_invalid"] += 1
            continue
        # Cached/offline clients are not evidence of a current IP assignment.
        if entry.get("isOnline") not in (True, 1, "1"):
            summary["clients_inactive"] += 1
            continue
        try:
            ip = ipaddress.ip_address(entry.get("ip", ""))
        except ValueError:
            summary["clients_invalid"] += 1
            continue
        if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            summary["clients_invalid"] += 1
            continue
        radio = str(entry.get("isWL", ""))
        connection = "Ethernet" if radio == "0" else {
            "1": "Wi-Fi 2.4 GHz", "2": "Wi-Fi 5 GHz", "3": "Wi-Fi 5 GHz", "4": "Wi-Fi 6 GHz",
        }.get(radio, "Unknown")
        try:
            rssi = int(entry.get("rssi"))
            rssi = rssi if -127 <= rssi < 0 and radio in {"1", "2", "3", "4"} else None
        except (TypeError, ValueError):
            rssi = None
        clients.append({
            "mac": mac, "ip": str(ip), "name": _text(entry.get("name")),
            "vendor": _text(entry.get("vendor")),
            "metadata": {"name": _text(entry.get("nickName")) or _text(entry.get("name")),
                         "connection": connection, "ssid": _text(entry.get("ssid")), "rssi": rssi},
        })
    # Skip every record involved in duplicate-IP data rather than guessing an owner.
    ip_counts = {}
    mac_counts = {}
    for client in clients:
        ip_counts[client["ip"]] = ip_counts.get(client["ip"], 0) + 1
        mac_counts[client["mac"]] = mac_counts.get(client["mac"], 0) + 1
    unique = [client for client in clients if ip_counts[client["ip"]] == 1 and mac_counts[client["mac"]] == 1]
    summary["clients_invalid"] += len(clients) - len(unique)
    summary["clients_active"] = len(unique)
    summary["model"] = _text(payload.get("productid"))
    summary["firmware"] = ".".join(filter(None, (_text(payload.get(key)) for key in ("firmver", "buildno", "extendno"))))
    return unique, summary


def inspect_asuswrt(url, username, password, verify_ssl=True):
    client = AsuswrtClient(url, username, password, verify_ssl)
    try:
        return parse_clients(client.fetch_clients())
    finally:
        client.close()


def _source(config):
    return (config.asuswrt_url, config.asuswrt_username, config.asuswrt_password,
            config.asuswrt_verify_ssl, config.asuswrt_create_devices)


def sync_asuswrt(*, manual=False):
    with serialized_database_write():
        config = AppSettings.load()
        if not config.asuswrt_enabled:
            return {"status": "disabled"}
        if config.asuswrt_auth_failed and not manual:
            return {"status": "auth_paused"}
        source = _source(config)
        try:
            observed_at = timezone.now()
            clients, summary = inspect_asuswrt(*source[:4])
            with transaction.atomic():
                config.refresh_from_db()
                if not config.asuswrt_enabled:
                    return {"status": "disabled"}
                if source != _source(config):
                    raise AsuswrtError("ASUSWRT settings changed during sync. Try again.")
                summary.update(apply_client_observations(
                    clients, observed_at, config.asuswrt_create_devices,
                    identity_source=Device.IdentitySource.ASUSWRT,
                    observation_reason="Observed in ASUSWRT client list; not verified by a LanGuard scan",
                ))
                summary["clients_enriched"] = 0
                for client in clients:
                    device = Device.objects.filter(mac=client["mac"], ip=client["ip"], archived=False).first()
                    if not device or device.identity_conflict_reason:
                        continue
                    device.asuswrt_data = {**client["metadata"], "observed_at": utc_isoformat(observed_at),
                                           "router_url": config.asuswrt_url, "model": summary["model"]}
                    fields = ["asuswrt_data"]
                    if not device.known and not device.vendor and client["vendor"]:
                        device.vendor, device.vendor_source = client["vendor"], Device.IdentitySource.ASUSWRT
                        fields.extend(["vendor", "vendor_source"])
                    device.save(update_fields=fields)
                    summary["clients_enriched"] += 1
                summary.update({"status": "ok", "observed_at": utc_isoformat(observed_at)})
                config.asuswrt_last_sync_at = timezone.now()
                config.asuswrt_last_sync_summary = summary
                config.asuswrt_last_error = ""
                config.asuswrt_auth_failed = False
                config.save(update_fields=["asuswrt_last_sync_at", "asuswrt_last_sync_summary",
                                           "asuswrt_last_error", "asuswrt_auth_failed", "updated_at"])
            return summary
        except AsuswrtError as exc:
            # Do not retain credentials, tokens, or raw router responses in diagnostics.
            config.refresh_from_db()
            if source == _source(config):
                config.asuswrt_last_error = str(exc)
                config.asuswrt_auth_failed = isinstance(exc, AsuswrtAuthError)
                config.save(update_fields=["asuswrt_last_error", "asuswrt_auth_failed", "updated_at"])
            raise
