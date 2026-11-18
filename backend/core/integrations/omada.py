"""Omada OpenAPI v1: client-credentials authentication and read-only inventory."""

import json
import re
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

import requests

from .unifi import ControllerError, normalize_ip, normalize_mac, text

PAGE_SIZE = 200
MAX_CLIENTS = 5000
MAX_SITES = 1000
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


def identifier(value):
    return value if isinstance(value, str) and IDENTIFIER.fullmatch(value) else ""


def normalize_url(value):
    try:
        value = value.strip()
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.path not in ("", "/") or parsed.port == 0
            or any(c.isspace() or not c.isprintable() or c in "\\?#" for c in value)
            or parsed.hostname.lower().rstrip(".").endswith((".tplinkcloud.com", ".omada.tplinkcloud.com"))
        ):
            raise ValueError
    except ValueError:
        raise ControllerError("Enter the local Omada HTTPS origin, without credentials, paths or query parameters.") from None
    return urlunsplit(("https", parsed.netloc.lower(), "", "", ""))


class OmadaProvider:
    def __init__(self, url, client_secret, verify_ssl, *, controller_id, client_id):
        self.origin = normalize_url(url)
        self.controller_id, self.client_id = identifier(controller_id), identifier(client_id)
        if not self.controller_id or not self.client_id or not client_secret:
            raise ControllerError("Enter the Omada controller ID, Client ID and Client Secret.")
        self.secret = client_secret
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.trust_env = False
        self.deadline = monotonic() + 25
        self.token = ""
        self.token_deadline = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.token = ""
        self.session.close()

    def _request(self, *, auth=False, site_id=None, page=1):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise ControllerError("Omada inventory collection timed out.")
        headers = {"Accept": "application/json"}
        if auth:
            path = "/openapi/authorize/token"
            params = {"grant_type": "client_credentials"}
            body = {"omadacId": self.controller_id, "client_id": self.client_id, "client_secret": self.secret}
        else:
            if not self.token or monotonic() >= self.token_deadline:
                raise ControllerError("Omada access token expired. Try synchronizing again.")
            if site_id is not None and not identifier(site_id):
                raise ControllerError("Invalid Omada site identifier.")
            path = f"/openapi/v1/{self.controller_id}/sites"
            if site_id is not None:
                path += f"/{site_id}/clients"
            params, body = {"page": page, "pageSize": PAGE_SIZE}, None
            headers["Authorization"] = f"AccessToken={self.token}"
        request = self.session.post if auth else self.session.get
        kwargs = {"json": body} if auth else {}
        try:
            with request(
                self.origin + path, params=params, headers=headers,
                timeout=(min(3, remaining), min(5, remaining)), verify=self.verify_ssl,
                allow_redirects=False, stream=True, **kwargs,
            ) as response:
                if response.status_code in (401, 403):
                    raise ControllerError("Omada denied access. Check Client mode credentials and site read permissions.")
                if not 200 <= response.status_code < 300:
                    raise ControllerError("Omada returned an unsuccessful HTTP response. Check the local OpenAPI URL and port.")
                content = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if monotonic() > self.deadline:
                        raise ControllerError("Omada inventory collection timed out.")
                    if len(content) + len(chunk) > 2 * 1024 * 1024:
                        raise ControllerError("Omada response exceeded the 2 MiB limit.")
                    content.extend(chunk)
                payload = json.loads(content)
        except requests.exceptions.SSLError:
            raise ControllerError("Omada TLS certificate could not be verified.") from None
        except requests.Timeout:
            raise ControllerError("Omada inventory collection timed out.") from None
        except requests.RequestException:
            raise ControllerError("Could not reach the Omada local OpenAPI.") from None
        except (ValueError, RecursionError):
            raise ControllerError("Omada did not return valid JSON.") from None
        if not isinstance(payload, dict):
            raise ControllerError("Omada returned an invalid OpenAPI response.")
        code = payload.get("errorCode")
        if type(code) is not int or code != 0:
            # Upstream messages can echo credentials or URLs; never retain them.
            raise ControllerError("Omada rejected the OpenAPI request. Check Client mode, controller ID, site privileges and firmware support.")
        if not isinstance(payload.get("result"), dict):
            raise ControllerError("Omada returned an invalid OpenAPI result.")
        return payload["result"]

    def _login(self):
        if self.token:
            return
        result = self._request(auth=True)
        token, ttl = result.get("accessToken"), result.get("expiresIn")
        if (
            not isinstance(token, str) or not 1 <= len(token) <= 4096
            or any(not 33 <= ord(c) <= 126 for c in token)
            or type(ttl) is not int or ttl <= 0
        ):
            raise ControllerError("Omada did not issue a valid access token.")
        self.token = token
        self.token_deadline = monotonic() + ttl

    def label(self, value, limit=128):
        if isinstance(value, str) and any(secret and secret in value for secret in (self.secret, self.token)):
            return ""
        return text(value, limit)

    def _list(self, *, site_id=None, maximum):
        self._login()
        result, expected_total, page = [], None, 1
        while True:
            payload = self._request(site_id=site_id, page=page)
            rows, total = payload.get("data"), payload.get("totalRows")
            if (
                not isinstance(rows, list) or len(rows) > PAGE_SIZE
                or type(total) is not int or not 0 <= total <= maximum
                or payload.get("currentPage") != page
                or (expected_total is not None and total != expected_total)
                or len(result) + len(rows) > total or (not rows and len(result) < total)
            ):
                raise ControllerError("Omada returned an inconsistent or oversized inventory page. No devices were changed.")
            result.extend(rows)
            if len(result) == total:
                return result
            if len(rows) != PAGE_SIZE:
                raise ControllerError("Omada returned an incomplete inventory page. No devices were changed.")
            expected_total, page = total, page + 1

    def list_sites(self):
        sites = {}
        for row in self._list(maximum=MAX_SITES):
            site_id = identifier(row.get("siteId")) if isinstance(row, dict) else ""
            if not site_id or site_id in sites or any(secret and secret in site_id for secret in (self.secret, self.token)):
                raise ControllerError("Omada returned an invalid or duplicate site identifier.")
            sites[site_id] = {"id": site_id, "name": self.label(row.get("name")) or "Unnamed site"}
        return list(sites.values())

    def _site(self, site_id):
        for site in self.list_sites():
            if site["id"] == site_id:
                return site
        raise ControllerError("The selected Omada site is not accessible. Refresh the site list.")

    def test_connection(self, site_id=None):
        if not site_id:
            return {"sites": self.list_sites()}
        site = self._site(site_id)
        rows = self._list(site_id=site["id"], maximum=MAX_CLIENTS)
        return {"site": site, "clients_reported": len(rows)}

    def sync_devices(self, site_id):
        site = self._site(site_id)
        rows = self._list(site_id=site["id"], maximum=MAX_CLIENTS)
        clients = []
        for row in rows:
            if not isinstance(row, dict) or row.get("active") is not True:
                continue
            mac = normalize_mac(row.get("mac"))
            if not mac:
                continue
            wireless = row.get("wireless")
            metadata = {"site_id": site["id"], "site_name": site["name"]}
            if type(wireless) is bool:
                metadata["connection"] = "WIRELESS" if wireless else "WIRED"
            uplink_type = row.get("connectDevType")
            uplink = {"ap": "ap", "switch": "switch", "gateway": "gateway"}.get(uplink_type)
            for field, value in {
                "name": self.label(row.get("name")), "ssid": self.label(row.get("ssid")) if wireless is True else "",
                "network": self.label(row.get("networkName")),
                "uplink": self.label(row.get(f"{uplink}Name")) or normalize_mac(row.get(f"{uplink}Mac")) if uplink else "",
            }.items():
                if value:
                    metadata[field] = value
            numeric = {
                "vlan": (row.get("vid"), 1, 4094),
                "switch_port": (row.get("port") if wireless is False else None, 1, 65535),
                "rssi": (row.get("rssi") if wireless is True else None, -127, -1),
                "signal_percent": (row.get("signalLevel") if wireless is True else None, 0, 100),
                "channel": (row.get("channel") if wireless is True else None, 1, 233),
            }
            for field, (value, low, high) in numeric.items():
                if type(value) is int and low <= value <= high:
                    metadata[field] = value
            if wireless is True and type(row.get("radioId")) is int:
                radio = {0: "2.4 GHz", 1: "5 GHz-1", 2: "5 GHz-2", 3: "6 GHz"}.get(row["radioId"])
                if radio:
                    metadata["radio"] = radio
            external_id = identifier(row.get("id"))
            if not external_id or any(secret and secret in external_id for secret in (self.secret, self.token)):
                external_id = mac
            clients.append({
                "mac": mac, "ip": normalize_ip(row.get("ip")), "external_id": external_id,
                "hostname": self.label(row.get("hostName"), 255), "vendor": self.label(row.get("vendor"), 255),
                "metadata": metadata,
            })
        return clients, len(rows)
