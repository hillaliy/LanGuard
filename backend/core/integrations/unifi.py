"""Official local UniFi Network Integration API (GET-only)."""

import ipaddress
import json
import re
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import UUID

import requests

API_PREFIXES = ("/proxy/network/integration/v1", "/integration/v1")
PAGE_SIZE = 200
MAX_CLIENTS = 5000
MAX_SITES = 1000


class ControllerError(RuntimeError):
    pass


class ControllerNotFound(ControllerError):
    pass


def normalize_url(value):
    try:
        value = value.strip()
        url = urlsplit(value)
        path = url.path.rstrip("/")
        if (
            url.scheme != "https" or not url.hostname or url.username is not None
            or any(c.isspace() or not c.isprintable() or c in "\\?#" for c in value)
            or url.port == 0 or path not in ("", *API_PREFIXES)
            or url.hostname.lower().rstrip(".") in {"api.ui.com", "unifi.ui.com"}
        ):
            raise ValueError
    except ValueError:
        raise ControllerError("Enter the local UniFi HTTPS origin or Integration API base URL.") from None
    return urlunsplit(("https", url.netloc.lower(), path, "", ""))


def safe_id(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        return ""


def text(value, limit=128):
    return "".join(c for c in value if c.isprintable()).strip()[:limit] if isinstance(value, str) else ""


def normalize_mac(value):
    value = text(value).lower()
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}|(?:[0-9a-f]{2}-){5}[0-9a-f]{2}|[0-9a-f]{12}", value):
        return ""
    raw = value.replace(":", "").replace("-", "")
    if int(raw[:2], 16) & 1 or int(raw, 16) == 0:
        return ""
    return ":".join(raw[n:n + 2] for n in range(0, 12, 2))


def normalize_ip(value):
    if not isinstance(value, str) or "%" in value:
        return ""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return ""
    return str(ip) if not (ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_reserved) else ""


class UniFiProvider:
    def __init__(self, url, api_key, verify_ssl):
        parsed = urlsplit(normalize_url(url))
        self.origin = urlunsplit(("https", parsed.netloc, "", "", ""))
        self.prefixes = (parsed.path,) if parsed.path else API_PREFIXES
        self.prefix = None
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.deadline = monotonic() + 25
        self.session = requests.Session()
        self.session.trust_env = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.session.close()

    def _get(self, prefix, path, offset=0, limit=PAGE_SIZE):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise ControllerError("UniFi inventory request timed out.")
        try:
            with self.session.get(
                self.origin + prefix + path, params={"offset": offset, "limit": limit},
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                timeout=(min(3, remaining), min(5, remaining)),
                verify=self.verify_ssl, allow_redirects=False, stream=True,
            ) as response:
                if response.status_code in (401, 403):
                    raise ControllerError("UniFi denied access. Check the local API key and site permissions.")
                if response.status_code == 404:
                    raise ControllerNotFound("UniFi endpoint or site was not found.")
                if not 200 <= response.status_code < 300:
                    raise ControllerError("UniFi returned an unsuccessful HTTP response. Check the API base URL.")
                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if monotonic() > self.deadline:
                        raise ControllerError("UniFi inventory request timed out.")
                    if len(body) + len(chunk) > 2 * 1024 * 1024:
                        raise ControllerError("UniFi inventory response exceeded the size limit.")
                    body.extend(chunk)
                payload = json.loads(body)
        except requests.exceptions.SSLError:
            raise ControllerError("UniFi TLS certificate could not be verified.") from None
        except requests.Timeout:
            raise ControllerError("UniFi inventory request timed out.") from None
        except requests.RequestException:
            raise ControllerError("Could not reach the UniFi local API.") from None
        except (ValueError, RecursionError):
            raise ControllerError("UniFi returned an invalid JSON response.") from None
        if not isinstance(payload, dict):
            raise ControllerError("UniFi returned an invalid inventory response.")
        return payload

    def _page(self, path, offset=0, limit=PAGE_SIZE):
        for prefix in (self.prefix,) if self.prefix else self.prefixes:
            try:
                payload = self._get(prefix, path, offset, limit)
            except ControllerNotFound:
                if self.prefix or prefix == self.prefixes[-1]:
                    raise
                continue
            self.prefix = prefix
            break
        rows, total = payload.get("data"), payload.get("totalCount")
        if (
            not isinstance(rows, list) or len(rows) > limit or type(total) is not int or total < 0
            or payload.get("offset") != offset or payload.get("count") != len(rows)
            or (not rows and offset < total) or (rows and offset + len(rows) > total)
        ):
            raise ControllerError("UniFi returned an invalid inventory page.")
        return rows, total

    def _list(self, path, maximum):
        rows = []
        while True:
            page, total = self._page(path, len(rows))
            if total > maximum or len(rows) + len(page) > maximum:
                raise ControllerError("UniFi inventory exceeds the supported record limit.")
            rows.extend(page)
            if len(rows) >= total:
                return rows

    def label(self, value, limit=128):
        # Never persist a key reflected by a misconfigured upstream endpoint.
        return text(value, limit) if not (isinstance(value, str) and self.api_key in value) else ""

    def list_sites(self):
        sites = {}
        for row in self._list("/sites", MAX_SITES):
            site_id = safe_id(row.get("id")) if isinstance(row, dict) else ""
            if not site_id:
                raise ControllerError("UniFi returned an invalid site identifier.")
            sites[site_id] = {"id": site_id, "name": self.label(row.get("name")) or "Unnamed site"}
        return list(sites.values())

    def _site(self, site_id):
        sites = self.list_sites()
        for site in sites:
            if site["id"] == safe_id(site_id):
                return site
        raise ControllerError("The selected UniFi site is not accessible. Refresh the site list.")

    def test_connection(self, site_id=None):
        if site_id:
            site = self._site(site_id)
            _, total = self._page(f"/sites/{site['id']}/clients", limit=1)
            return {"site": site, "clients_reported": total}
        return {"sites": self.list_sites()}

    def _client_url(self, value):
        value = self.label(value, 2048)
        if not value or any(c in value for c in "\\?#") or any(c.isspace() for c in value):
            return ""
        try:
            url = urlsplit(urljoin(self.origin, value))
            if url.scheme == "https" and url.netloc == urlsplit(self.origin).netloc and url.path.startswith("/network/"):
                return url.geturl()
        except ValueError:
            pass
        return ""

    def sync_devices(self, site_id):
        site = self._site(site_id)
        path = f"/sites/{site['id']}"
        rows = self._list(path + "/clients", MAX_CLIENTS)
        uplinks = {}
        if any(isinstance(row, dict) and safe_id(row.get("uplinkDeviceId")) for row in rows):
            try:
                uplinks = {
                    safe_id(row.get("id")): self.label(row.get("name"))
                    for row in self._list(path + "/devices", MAX_CLIENTS)
                    if isinstance(row, dict) and safe_id(row.get("id"))
                }
            except ControllerError:
                # A key can be scoped to clients without adopted-device access.
                pass
        clients = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mac, external_id = normalize_mac(row.get("macAddress")), safe_id(row.get("id"))
            if not mac or not external_id:
                continue
            uplink_id = safe_id(row.get("uplinkDeviceId"))
            metadata = {"site_id": site["id"], "site_name": site["name"]}
            for key, value in {
                "name": self.label(row.get("name")),
                "connection": self.label(row.get("type"), 24),
                "ssid": self.label(row.get("ssid")),
                "network": self.label(row.get("networkName")) or safe_id(row.get("networkId")),
                "uplink": uplinks.get(uplink_id) or uplink_id,
                "client_url": self._client_url(row.get("clientUrl")),
            }.items():
                if value:
                    metadata[key] = value
            for key, (value, low, high) in {
                "vlan": (row.get("vlanId"), 1, 4094),
                "switch_port": (row.get("switchPort"), 1, 65535),
                "rssi": (row.get("signalDbm"), -127, -1),
            }.items():
                if type(value) is int and low <= value <= high:
                    metadata[key] = value
            clients.append({
                "mac": mac, "external_id": external_id, "ip": normalize_ip(row.get("ipAddress")),
                "hostname": self.label(row.get("hostname"), 255),
                "vendor": self.label(row.get("vendor"), 255), "metadata": metadata,
            })
        return clients, len(rows)
