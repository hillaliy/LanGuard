"""Bounded RouterOS 7 REST reads. Leases and bridge entries are not liveness."""

import base64
import json
import re
from collections import defaultdict
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

import requests

from .unifi import ControllerError, normalize_ip, normalize_mac, text

# Explicit property lists avoid collecting configuration secrets and unrelated data.
MENUS = {
    "system/resource": "version",
    "system/identity": "name",
    "ip/arp": "address,mac-address,interface,status,disabled,invalid,published",
    "ip/dhcp-server/lease": "mac-address,active-mac-address,address,active-address,host-name,status,server,disabled",
    "interface/bridge/host": "mac-address,on-interface,bridge,vid,local,invalid",
    "interface/wifi/registration-table": "mac-address,interface,authorized,ssid,signal,vlan-id",
    "interface/wireless/registration-table": "mac-address,interface,ap,signal-strength",
    "caps-man/registration-table": "mac-address,interface,ssid,rx-signal",
}
MAX_ROWS = 5000


def normalize_url(value):
    try:
        value = value.strip()
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.path not in ("", "/") or parsed.port == 0
                or any(c.isspace() or not c.isprintable() or c in "\\?#" for c in value)):
            raise ValueError
    except ValueError:
        raise ControllerError("Enter the RouterOS HTTPS origin without credentials, paths or query parameters.") from None
    return urlunsplit(("https", parsed.netloc.lower(), "", "", ""))


def yes(value):
    return value is True or value in ("true", "yes")


def number(value, low, high):
    if isinstance(value, bool) or not re.fullmatch(r"-?\d{1,6}", str(value)):
        return None
    value = int(value)
    return value if low <= value <= high else None


class RouterOSProvider:
    def __init__(self, url, password, verify_ssl, *, username):
        self.origin = normalize_url(url)
        if (not username or not password or ":" in username
                or any(not 32 <= ord(c) <= 126 for c in username + password)):
            raise ControllerError("Enter the RouterOS username and password.")
        self.password, self.username, self.verify_ssl = password, username, verify_ssl
        self.encoded_auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session = requests.Session()
        self.session.trust_env = False
        self.deadline = monotonic() + 25
        self.warnings = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.session.close()

    def label(self, value, limit=128):
        return "" if isinstance(value, str) and any(secret in value for secret in (
            self.password, self.encoded_auth,
        )) else text(value, limit)

    def _read(self, menu, *, optional=False):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise ControllerError("RouterOS inventory collection timed out.")
        try:
            with self.session.get(
                self.origin + "/rest/" + menu, params={".proplist": MENUS[menu]},
                auth=(self.username, self.password), headers={"Accept": "application/json"},
                verify=self.verify_ssl, timeout=(min(3, remaining), min(5, remaining)),
                allow_redirects=False, stream=True,
            ) as response:
                if response.status_code in (401, 403):
                    raise ControllerError("RouterOS denied access. Check credentials and read, api, rest-api permissions.")
                if response.status_code == 404 and optional:
                    self.warnings.append(f"Unavailable menu: {menu}")
                    return []
                if not 200 <= response.status_code < 300:
                    raise ControllerError("RouterOS returned an unsuccessful HTTP response. Check the HTTPS REST service.")
                content = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if monotonic() > self.deadline:
                        raise ControllerError("RouterOS inventory collection timed out.")
                    if len(content) + len(chunk) > 2 * 1024 * 1024:
                        raise ControllerError("RouterOS response exceeded the 2 MiB limit.")
                    content.extend(chunk)
                data = json.loads(content)
        except requests.exceptions.SSLError:
            raise ControllerError("RouterOS TLS certificate could not be verified.") from None
        except requests.Timeout:
            raise ControllerError("RouterOS inventory collection timed out.") from None
        except requests.RequestException:
            raise ControllerError("Could not reach the RouterOS HTTPS REST service.") from None
        except (ValueError, RecursionError):
            raise ControllerError("RouterOS did not return valid JSON.") from None
        if not isinstance(data, list) or len(data) > MAX_ROWS or any(not isinstance(row, dict) for row in data):
            raise ControllerError("RouterOS returned an invalid or oversized inventory. No devices were changed.")
        return data

    def _router(self):
        resources = self._read("system/resource")
        version = resources[0].get("version", "") if len(resources) == 1 else ""
        match = re.match(r"^7\.(\d+)(?:\.|\s|$)", str(version))
        if not match or int(match[1]) < 1:
            raise ControllerError("This integration requires RouterOS 7.1 or newer stable 7.x with HTTPS REST.")
        identity = self._read("system/identity")
        return self.label(identity[0].get("name")) if len(identity) == 1 else ""

    def list_sites(self):
        raise ControllerError("RouterOS connects directly to one router; it does not use controller sites.")

    def test_connection(self, site_id=None):
        rows, total = self.sync_devices(None)
        return {"clients_reported": total, "positive_observations": sum(row["presence"] for row in rows),
                "warnings": self.warnings}

    def sync_devices(self, site_id=None):
        router = self._router()
        by_mac = defaultdict(list)
        sources = ("ip/arp", "ip/dhcp-server/lease", "interface/bridge/host",
                   "interface/wifi/registration-table", "interface/wireless/registration-table",
                   "caps-man/registration-table")
        total = 0
        for menu in sources:
            rows = self._read(menu, optional=True)
            total += len(rows)
            if total > MAX_ROWS:
                raise ControllerError("RouterOS inventory exceeded the 5000 row limit. No devices were changed.")
            for row in rows:
                if any(yes(row.get(flag)) for flag in ("disabled", "invalid", "local", "published")):
                    continue
                lease = menu == "ip/dhcp-server/lease"
                if lease and row.get("status") != "bound":
                    continue
                mac = normalize_mac(row.get("active-mac-address") or row.get("mac-address"))
                if mac:
                    by_mac[mac].append((menu, row))
        if len(self.warnings) == len(sources):
            raise ControllerError("RouterOS exposes no supported inventory menus. Check REST access and installed packages.")
        clients = []
        for mac, entries in by_mac.items():
            ips, interfaces, bridges, vlans = set(), set(), set(), set()
            meta = {"router": router}
            positive, hostname = False, ""
            wifi_entries = []
            lease_entries = 0
            for menu, row in entries:
                if menu == "ip/dhcp-server/lease":
                    lease_entries += 1
                    ip = normalize_ip(row.get("active-address") or row.get("address"))
                    hostname = self.label(row.get("host-name"), 255)
                    meta.update(dhcp_server=self.label(row.get("server")), lease_status="bound")
                    if hostname:
                        meta["name"] = hostname
                    if ip:
                        ips.add(ip)
                elif menu == "ip/arp":
                    if row.get("status") == "reachable":
                        positive = True
                        ip = normalize_ip(row.get("address"))
                        if ip:
                            ips.add(ip)
                        meta["presence_evidence"] = "Reachable ARP"
                    meta["arp_status"] = self.label(row.get("status"))
                elif menu == "interface/bridge/host":
                    bridge = self.label(row.get("bridge"))
                    if bridge:
                        bridges.add(bridge)
                    interface = self.label(row.get("on-interface"))
                    if interface:
                        interfaces.add(interface)
                    vlan = number(row.get("vid"), 1, 4094)
                    if vlan:
                        vlans.add(vlan)
                else:
                    # New WiFi has an explicit authorization flag. Legacy tables list
                    # associated peers; exclude station uplinks from client discovery.
                    active = yes(row.get("authorized")) if menu.startswith("interface/wifi/") else (
                        row.get("ap") in (False, "false", "no") if menu.startswith("interface/wireless/") else True
                    )
                    if active:
                        wifi_entries.append(row)
            if (len(ips) > 1 or len(wifi_entries) > 1 or len(vlans) > 1 or lease_entries > 1
                    or len(interfaces) > 1 or len(bridges) > 1):
                # Ambiguous VLAN/IP or simultaneous registration observations cannot
                # safely identify the current attachment of a global inventory MAC.
                continue
            if wifi_entries:
                row = wifi_entries[0]
                positive = True
                meta.update(connection="WIRELESS", presence_evidence="Wi-Fi registration",
                            interface=self.label(row.get("interface")), ssid=self.label(row.get("ssid")))
                signal = row.get("signal", row.get("signal-strength", row.get("rx-signal")))
                signal = str(signal).split("dBm", 1)[0]
                rssi = number(signal, -127, -1)
                if rssi is not None:
                    meta["rssi"] = rssi
                vlan = number(row.get("vlan-id"), 1, 4094)
                if vlan:
                    if vlans and vlan not in vlans:
                        continue
                    vlans.add(vlan)
            elif len(interfaces) == 1:
                meta["interface"] = next(iter(interfaces))
            if vlans:
                meta["vlan"] = next(iter(vlans))
            if bridges:
                meta["bridge"] = next(iter(bridges))
            ip = next(iter(ips), "")
            if ip:
                meta["reported_ip"] = ip
            clients.append({"mac": mac, "ip": ip, "external_id": mac, "hostname": hostname,
                            "vendor": "", "presence": positive,
                            "metadata": {key: value for key, value in meta.items() if value != ""}})
        # A MAC can occur in several RouterOS tables; report normalized clients plus
        # rejected rows, not every successful join as a skipped device.
        return clients, len(by_mac)
