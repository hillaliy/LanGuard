import logging
import ipaddress
import os
import random
import re
import socket
import struct
import time
import warnings
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
import requests
import scapy.all as scapy
from scapy.data import ManufDA
from urllib3.exceptions import InsecureRequestWarning

from .models import Device, DevicePort, NetworkEvent, ScanRun
from .notifications import notify_event


LOGGER = logging.getLogger(__name__)
DEFAULT_DEVICE_NAME = "Device"
DEFAULT_DEVICE_ICONS = {"", "plus", "unknown", "device", "desktop"}
SSDP_CACHE_TTL_SECONDS = 10
SSDP_HOSTNAME_CACHE = {"expires_at": 0.0, "hostnames": {}}
MDNS_SERVICE_CACHE_TTL_SECONDS = 10
MDNS_SERVICE_HOSTNAME_CACHE = {"expires_at": 0.0, "hostnames": {}}
MDNS_SERVICE_TIMEOUT_SECONDS = 1.8
MDNS_SERVICE_RETRY_COUNT = 3
MDNS_SERVICE_RETRY_DELAY_SECONDS = 0.25
MDNS_SERVICE_TYPES = (
    "_hap._tcp.local",
    "_services._dns-sd._udp.local",
    "_http._tcp.local",
    "_arduino._tcp.local",
    "_esphomelib._tcp.local",
    "_workstation._tcp.local",
    "_ssh._tcp.local",
)
WEB_INTERFACE_PORTS = (
    (443, "https"),
    (80, "http"),
    (8443, "https"),
    (8080, "http"),
    (8000, "http"),
    (8888, "http"),
)
DEVICE_GUESS_RULES = [
    {
        "icon": "smart-hub",
        "keywords": (
            "smart hub",
            "home hub",
            "smart bridge",
            "home bridge",
        ),
    },
    {
        "icon": "router",
        "keywords": (
            "router",
            "gateway",
            "access point",
            "wireless ap",
            "wifi ap",
            "mesh",
        ),
    },
    {
        "icon": "phone",
        "keywords": ("phone", "mobile"),
    },
    {
        "icon": "tablet",
        "keywords": ("tablet",),
    },
    {
        "icon": "smart-watch",
        "keywords": ("watch", "smartwatch", "wearable"),
    },
    {
        "icon": "laptop",
        "keywords": ("laptop", "notebook"),
    },
    {
        "icon": "streamer",
        "keywords": ("streamer", "streaming"),
        "ports": (8008, 8009),
    },
    {
        "icon": "tv",
        "keywords": ("tv", "television"),
    },
    {
        "icon": "security-camera",
        "keywords": ("camera", "cam", "cctv"),
        "ports": (554,),
    },
    {
        "icon": "shutter",
        "keywords": ("shutter", "roller shutter"),
    },
    {
        "icon": "blinds",
        "keywords": ("blind", "blinds", "shade", "curtain"),
    },
    {
        "icon": "led-strip",
        "keywords": ("led strip", "light strip", "strip light"),
    },
    {
        "icon": "desk-lamp",
        "keywords": ("desk lamp", "table lamp", "reading lamp"),
    },
    {
        "icon": "ceiling-light",
        "keywords": ("ceiling light", "downlight"),
    },
    {
        "icon": "light",
        "keywords": ("light", "bulb", "lamp"),
    },
    {
        "icon": "air-conditioner",
        "keywords": ("air conditioner", "air-conditioning", "aircon", "hvac"),
    },
    {
        "icon": "ceiling-fan",
        "keywords": ("ceiling fan",),
    },
    {
        "icon": "fan",
        "keywords": ("fan",),
    },
    {
        "icon": "thermostat",
        "keywords": ("thermostat", "heater"),
    },
    {
        "icon": "speaker",
        "keywords": ("speaker", "audio"),
    },
    {
        "icon": "printer",
        "keywords": ("printer",),
        "ports": (9100,),
    },
    {
        "icon": "server",
        "keywords": ("server", "nas"),
        "ports": (22,),
    },
]

MANUF_PATHS = (
    os.path.join(os.path.dirname(__file__), "resources", "manuf"),
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "macos",
            "LanGuardMac",
            "Resources",
            "manuf",
        )
    ),
)


def mac_bytes(mac):
    parts = (mac or "").replace("-", ":").split(":")
    if len(parts) != 6:
        return None
    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError:
        return None


def is_locally_administered_mac(mac):
    raw = mac_bytes(mac)
    return bool(raw and raw[0] & 0x02)


class ManufVendorDB:
    _entries = None

    @classmethod
    def entries(cls):
        if cls._entries is None:
            cls._entries = cls.load_entries()
        return cls._entries

    @classmethod
    def load_entries(cls):
        entries = []
        for path in MANUF_PATHS:
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as manuf_file:
                    for line in manuf_file:
                        entry = cls.parse_line(line)
                        if entry:
                            entries.append(entry)
            except OSError as exc:
                LOGGER.debug("Failed reading manuf database %s: %s", path, exc)
            if entries:
                break
        return sorted(entries, key=lambda item: item[1], reverse=True)

    @staticmethod
    def parse_line(line):
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split(None, 2)
        if len(parts) < 2:
            return None
        prefix_text = parts[0]
        vendor = parts[2].strip() if len(parts) > 2 else parts[1].strip()
        if not vendor:
            return None
        if "/" in prefix_text:
            prefix_text, bits_text = prefix_text.split("/", 1)
            try:
                prefix_bits = int(bits_text)
            except ValueError:
                return None
        else:
            prefix_bits = len(prefix_text.replace(":", "").replace("-", "")) * 4
        try:
            prefix_value = int(prefix_text.replace(":", "").replace("-", ""), 16)
        except ValueError:
            return None
        prefix_hex_bits = len(prefix_text.replace(":", "").replace("-", "")) * 4
        if prefix_hex_bits > prefix_bits:
            prefix_value >>= prefix_hex_bits - prefix_bits
        return prefix_value, prefix_bits, vendor

    @classmethod
    def lookup(cls, mac):
        raw = mac_bytes(mac)
        if not raw or is_locally_administered_mac(mac):
            return ""
        mac_value = int.from_bytes(raw, "big")
        for prefix_value, prefix_bits, vendor in sorted(
            cls.entries(),
            key=lambda item: item[1],
            reverse=True,
        ):
            shift = 48 - prefix_bits
            if shift < 0:
                continue
            if (mac_value >> shift) == prefix_value:
                return vendor
        return ""


def manuf_vendor(mac):
    return ManufVendorDB.lookup(mac)


def dns_encode_name(name):
    encoded = bytearray()
    for label in name.strip(".").split("."):
        label_bytes = label.encode("ascii", "ignore")[:63]
        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)
    encoded.append(0)
    return bytes(encoded)


def dns_query_packet(name, query_type=12, query_id=None, query_class=1):
    query_id = random.randint(1, 65535) if query_id is None else query_id
    header = struct.pack("!HHHHHH", query_id, 0, 1, 0, 0, 0)
    question = dns_encode_name(name) + struct.pack("!HH", query_type, query_class)
    return header + question


def dns_read_name(packet, offset):
    labels = []
    jumped = False
    end_offset = offset
    seen_offsets = set()

    while offset < len(packet):
        length = packet[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end_offset = offset
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                break
            pointer = ((length & 0x3F) << 8) | packet[offset + 1]
            if pointer in seen_offsets:
                break
            seen_offsets.add(pointer)
            if not jumped:
                end_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        offset += 1
        label = packet[offset : offset + length].decode("utf-8", "ignore")
        labels.append(label)
        offset += length
        if not jumped:
            end_offset = offset

    return ".".join(label for label in labels if label), end_offset


def dns_ptr_names(packet, expected_owner=""):
    if len(packet) < 12:
        return []
    normalized_expected_owner = (expected_owner or "").strip().lower().rstrip(".")
    try:
        qdcount, ancount, nscount, arcount = struct.unpack("!HHHH", packet[4:12])
    except struct.error:
        return []
    offset = 12
    for _ in range(qdcount):
        _, offset = dns_read_name(packet, offset)
        offset += 4
    names = []
    for _ in range(ancount + nscount + arcount):
        owner, offset = dns_read_name(packet, offset)
        if offset + 10 > len(packet):
            break
        record_type, _, _, rdlength = struct.unpack("!HHIH", packet[offset : offset + 10])
        offset += 10
        rdata_offset = offset
        offset += rdlength
        if record_type == 12:
            normalized_owner = owner.strip().lower().rstrip(".")
            if normalized_expected_owner and normalized_owner != normalized_expected_owner:
                continue
            name, _ = dns_read_name(packet, rdata_offset)
            if name:
                names.append(name)
    return names


def dns_records(packet):
    if len(packet) < 12:
        return []
    try:
        qdcount, ancount, nscount, arcount = struct.unpack("!HHHH", packet[4:12])
    except struct.error:
        return []
    offset = 12
    for _ in range(qdcount):
        _, offset = dns_read_name(packet, offset)
        offset += 4
    records = []
    for _ in range(ancount + nscount + arcount):
        name, offset = dns_read_name(packet, offset)
        if offset + 10 > len(packet):
            break
        record_type, record_class, ttl, rdlength = struct.unpack("!HHIH", packet[offset : offset + 10])
        offset += 10
        rdata_offset = offset
        offset += rdlength
        if offset > len(packet):
            break
        records.append(
            {
                "name": name,
                "type": record_type,
                "class": record_class,
                "ttl": ttl,
                "rdata_offset": rdata_offset,
                "rdlength": rdlength,
            }
        )
    return records


def reverse_dns_name(ip):
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if address.version != 4:
        return ""
    return ".".join(reversed(ip.split("."))) + ".in-addr.arpa"


def udp_exchange(packet, address, port, timeout):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (address, port))
        response, _ = sock.recvfrom(2048)
        return response


def udp_responses(packet, address, port, timeout, max_responses=12):
    responses = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (address, port))
        while len(responses) < max_responses:
            try:
                response, source = sock.recvfrom(4096)
            except socket.timeout:
                break
            responses.append((response, source[0]))
    return responses


def mdns_legacy_responses(packets, timeout, max_responses=48):
    """Send one-shot mDNS queries from an ephemeral port and collect unicast replies."""
    responses = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("B", 255))
        for packet in packets:
            sock.sendto(packet, ("224.0.0.251", 5353))

        deadline = time.monotonic() + timeout
        while len(responses) < max_responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(max(0.05, remaining))
            try:
                response, source = sock.recvfrom(9000)
            except socket.timeout:
                break
            responses.append((response, source[0]))
    return responses


def mdns_multicast_responses(packets, timeout, max_responses=48):
    responses = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.bind(("", 5353))
        membership = socket.inet_aton("224.0.0.251") + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("B", 255))

        for packet in packets:
            sock.sendto(packet, ("224.0.0.251", 5353))

        deadline = time.monotonic() + timeout
        while len(responses) < max_responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(max(0.05, remaining))
            try:
                response, source = sock.recvfrom(4096)
            except socket.timeout:
                break
            responses.append((response, source[0]))
    return responses


def mdns_reverse_hostname(ip):
    name = reverse_dns_name(ip)
    if not name:
        return ""
    packet = dns_query_packet(name, query_type=12)
    responses = []
    try:
        responses.extend(mdns_legacy_responses([packet], 0.8, max_responses=8))
    except OSError as exc:
        LOGGER.debug("mDNS legacy reverse lookup failed for %s: %s", ip, exc)
    try:
        responses.append((udp_exchange(packet, ip, 5353, 0.7), ip))
    except OSError as exc:
        LOGGER.debug("mDNS direct reverse lookup failed for %s: %s", ip, exc)
    for response, _ in responses:
        for ptr_name in dns_ptr_names(response, expected_owner=name):
            cleaned = clean_hostname(ptr_name, ip_address=ip)
            if cleaned:
                return cleaned
    return ""


def mdns_query_responses(service_types):
    responses = []
    legacy_packets = [
        dns_query_packet(service_type, query_type=12)
        for service_type in service_types
    ]
    try:
        responses.extend(
            mdns_legacy_responses(
                legacy_packets,
                MDNS_SERVICE_TIMEOUT_SECONDS,
                max_responses=96,
            )
        )
    except OSError as exc:
        LOGGER.debug("mDNS one-shot service lookup failed: %s", exc)

    multicast_packets = [
        dns_query_packet(service_type, query_type=12, query_id=0)
        for service_type in service_types
    ]
    try:
        responses.extend(
            mdns_multicast_responses(
                multicast_packets,
                MDNS_SERVICE_TIMEOUT_SECONDS,
                max_responses=96,
            )
        )
    except OSError as exc:
        LOGGER.debug("mDNS multicast service lookup failed: %s", exc)
    return responses


def mdns_service_hostname(ip):
    return mdns_service_hostname_map().get(ip, "")


def mdns_service_hostname_map():
    now = time.monotonic()
    if MDNS_SERVICE_HOSTNAME_CACHE["expires_at"] > now:
        return dict(MDNS_SERVICE_HOSTNAME_CACHE["hostnames"])

    hostnames_by_ip = {}
    responses = []
    service_types = set(MDNS_SERVICE_TYPES)
    for attempt in range(MDNS_SERVICE_RETRY_COUNT):
        attempt_responses = mdns_query_responses(sorted(service_types))
        responses.extend(attempt_responses)
        for response, _ in attempt_responses:
            service_types.update(mdns_service_types_from_response(response))
        if attempt + 1 < MDNS_SERVICE_RETRY_COUNT:
            time.sleep(MDNS_SERVICE_RETRY_DELAY_SECONDS)

    hostnames_by_ip.update(mdns_service_hostnames_from_responses(responses))
    for response, source_ip in responses:
        if source_ip not in hostnames_by_ip:
            hostname = mdns_service_hostname_from_response(response)
            if hostname:
                hostnames_by_ip[source_ip] = hostname
    MDNS_SERVICE_HOSTNAME_CACHE["expires_at"] = time.monotonic() + MDNS_SERVICE_CACHE_TTL_SECONDS
    MDNS_SERVICE_HOSTNAME_CACHE["hostnames"] = dict(hostnames_by_ip)
    return hostnames_by_ip


def mdns_service_hostnames_from_response(response):
    return mdns_service_hostnames_from_responses([(response, "")])


def mdns_service_hostnames_from_responses(responses):
    address_records = []
    service_names_by_target = {}
    for response, _ in responses:
        for record in dns_records(response):
            if record["type"] == 1 and record["rdlength"] == 4:
                rdata = response[record["rdata_offset"] : record["rdata_offset"] + 4]
                ip_address = ".".join(str(part) for part in rdata)
                address_records.append((record["name"], ip_address))
            elif record["type"] == 33:
                target = dns_srv_target_name(response, record["rdata_offset"], record["rdlength"])
                service_hostname = service_instance_hostname(record["name"])
                if target and service_hostname:
                    service_names_by_target[target.strip().lower().rstrip(".")] = service_hostname

    hostnames_by_ip = {}
    for host, ip_address in address_records:
        hostname = service_names_by_target.get(host.strip().lower().rstrip(".")) or clean_hostname(host)
        if hostname and hostname != ip_address:
            hostnames_by_ip[ip_address] = hostname
    return hostnames_by_ip


def mdns_service_types_from_response(response):
    service_types = set()
    for record in dns_records(response):
        if record["type"] != 12:
            continue
        service_name, _ = dns_read_name(response, record["rdata_offset"])
        normalized = service_name.strip().lower().rstrip(".")
        if re.fullmatch(r"_[^.]+\._(?:tcp|udp)\.local", normalized):
            service_types.add(normalized)
    return service_types


def mdns_service_hostname_from_response(response):
    for record in dns_records(response):
        if record["type"] == 33:
            hostname = service_instance_hostname(record["name"])
            if hostname:
                return hostname
        if record["type"] == 12:
            service_name, _ = dns_read_name(response, record["rdata_offset"])
            hostname = service_instance_hostname(service_name)
            if hostname:
                return hostname
    return ""


def dns_srv_target_name(packet, offset, length):
    if length < 7:
        return ""
    name, _ = dns_read_name(packet, offset + 6)
    return name


def service_instance_hostname(name):
    cleaned_name = (name or "").strip().rstrip(".")
    match = re.match(r"^(.+)\._[^.]+\._(?:tcp|udp)\.local$", cleaned_name, re.IGNORECASE)
    return clean_hostname(match.group(1)) if match else ""


def llmnr_reverse_hostname(ip):
    name = reverse_dns_name(ip)
    if not name:
        return ""
    packet = dns_query_packet(name, query_type=12, query_id=0x4C47)
    responses = []
    for address in ("224.0.0.252", ip):
        try:
            responses.append(udp_exchange(packet, address, 5355, 0.6))
        except OSError as exc:
            LOGGER.debug("LLMNR reverse lookup failed for %s via %s: %s", ip, address, exc)
    for response in responses:
        for ptr_name in dns_ptr_names(response, expected_owner=name):
            cleaned = clean_hostname(ptr_name)
            if cleaned:
                return cleaned
    return ""


def netbios_hostname(ip):
    transaction_id = random.randint(1, 65535)
    encoded_star = b" CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00"
    packet = (
        struct.pack("!HHHHHH", transaction_id, 0, 1, 0, 0, 0)
        + encoded_star
        + struct.pack("!HH", 0x0021, 0x0001)
    )
    try:
        response = udp_exchange(packet, ip, 137, 0.7)
    except OSError as exc:
        LOGGER.debug("NetBIOS hostname lookup failed for %s: %s", ip, exc)
        return ""
    if len(response) < 57:
        return ""
    name_count = response[56]
    offset = 57
    for _ in range(name_count):
        if offset + 18 > len(response):
            break
        raw_name = response[offset : offset + 15].decode("ascii", "ignore").strip()
        suffix = response[offset + 15]
        flags = struct.unpack("!H", response[offset + 16 : offset + 18])[0]
        offset += 18
        is_group = bool(flags & 0x8000)
        if raw_name and raw_name != "*" and suffix in (0x00, 0x20) and not is_group:
            return clean_hostname(raw_name)
    return ""


def ssdp_hostname(ip):
    return ssdp_hostname_map().get(ip, "")


def ssdp_hostname_map():
    now = time.monotonic()
    if SSDP_HOSTNAME_CACHE["expires_at"] > now:
        return dict(SSDP_HOSTNAME_CACHE["hostnames"])

    packet = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 1\r\n"
        "ST: ssdp:all\r\n"
        "USER-AGENT: LanGuard/1.0 UPnP/1.1\r\n"
        "\r\n"
    ).encode("ascii")
    try:
        responses = udp_responses(packet, "239.255.255.250", 1900, 0.7)
    except OSError as exc:
        LOGGER.debug("SSDP lookup failed: %s", exc)
        return {}

    hostnames = {}
    for response, source_ip in responses:
        hostname = ssdp_hostname_from_response(response, source_ip)
        if hostname:
            hostnames[source_ip] = hostname

    SSDP_HOSTNAME_CACHE["expires_at"] = now + SSDP_CACHE_TTL_SECONDS
    SSDP_HOSTNAME_CACHE["hostnames"] = hostnames
    return dict(hostnames)


def ssdp_hostname_from_response(response, ip):
    text = response.decode("utf-8", "ignore")
    headers = parse_http_headers(text)
    location = headers.get("location", "")
    if not location:
        return ""
    parsed = urlparse(location)
    if parsed.hostname and parsed.hostname != ip:
        return ""
    try:
        result = requests.get(location, timeout=1.0, headers={"User-Agent": "LanGuard/1.0"})
    except requests.RequestException as exc:
        LOGGER.debug("SSDP device description fetch failed for %s: %s", ip, exc)
        return ""
    body = result.text[:128_000]
    return hostname_from_device_description(body, ip)


def parse_http_headers(text):
    headers = {}
    for line in text.splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def hostname_from_device_description(body, ip=""):
    for tag in ("friendlyName", "modelName"):
        match = re.search(rf"<{tag}>\s*([^<]+)\s*</{tag}>", body or "", re.IGNORECASE)
        if not match:
            continue
        hostname = clean_hostname(match.group(1))
        if hostname and hostname != ip:
            return hostname
    return ""


def web_interface_candidates(ip, open_ports):
    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError:
        return []
    if not (parsed_ip.is_private or parsed_ip.is_link_local):
        return []

    host = f"[{parsed_ip}]" if parsed_ip.version == 6 else str(parsed_ip)
    available_ports = {int(port) for port in open_ports}
    candidates = []
    for port, scheme in WEB_INTERFACE_PORTS:
        if port not in available_ports:
            continue
        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        suffix = "" if default_port else f":{port}"
        candidates.append(f"{scheme}://{host}{suffix}")
    return candidates


def detect_web_interface(ip, open_ports, timeout=1.2):
    for url in web_interface_candidates(ip, open_ports):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InsecureRequestWarning)
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "LanGuard/1.0"},
                    allow_redirects=False,
                    stream=True,
                    verify=False,
                )
        except requests.RequestException as exc:
            LOGGER.debug("Web interface probe failed for %s: %s", url, exc)
            continue
        response.close()
        return url
    return ""


def get_hostname(ip, hostname_hints=None):
    lookup_steps = [reverse_dns_hostname, mdns_reverse_hostname]
    if hostname_hints is None:
        lookup_steps.extend((mdns_service_hostname, llmnr_reverse_hostname, ssdp_hostname))
    else:
        lookup_steps.extend((lambda address: hostname_hints.get(address, ""), llmnr_reverse_hostname))
    lookup_steps.append(netbios_hostname)
    for lookup in lookup_steps:
        hostname = lookup(ip)
        if hostname:
            return hostname
    return ""


def discover_hostname_hints():
    hints = ssdp_hostname_map()
    hints.update(mdns_service_hostname_map())
    return hints


def reverse_dns_hostname(ip):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return clean_hostname(hostname)
    except (socket.herror, socket.gaierror, TimeoutError, OSError) as e:
        LOGGER.debug("Reverse DNS hostname lookup failed for %s: %s", ip, e)
        return ""


def clean_hostname(hostname, ip_address=""):
    hostname = (hostname or "").strip().rstrip(".")
    lowered = hostname.lower()
    invalid_values = {"", "?", "in", "internet", "ptr", "a", "aaaa"}
    invalid_fragments = (
        "connection timed out",
        "no servers could be reached",
        "communications error",
        "operation timed out",
        "timed out",
        "nxdomain",
        "server can't find",
        "not found",
        "in-addr.arpa",
    )
    if (
        lowered in invalid_values
        or hostname == ip_address
        or hostname.startswith(";")
        or hostname.isdigit()
        or any(fragment in lowered for fragment in invalid_fragments)
    ):
        return ""
    return hostname.split(".")[0].replace("-", " ").strip()


def trim_vendor(vendor):
    return (vendor or "").strip()


def guess_text(*values):
    return (
        " ".join(value or "" for value in values)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def canonical_vendor(vendor=""):
    return trim_vendor(vendor)


def preferred_vendor(observed_vendor=""):
    return canonical_vendor(observed_vendor) or ""


def open_port_numbers(open_ports=None):
    ports = set()
    for port in open_ports or []:
        if isinstance(port, dict):
            value = port.get("port")
        else:
            value = port
        try:
            ports.add(int(value))
        except (TypeError, ValueError):
            continue
    return ports


def vendor_display_name(vendor):
    return trim_vendor(vendor)


def mac_suffix(mac, length=4):
    cleaned = "".join(character for character in (mac or "") if character.isalnum())
    return cleaned[-length:].upper() if cleaned else ""


def is_mac_address_text(value):
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return False
    compact = cleaned.replace(":", "").replace("-", "")
    return len(compact) == 12 and all(character in "0123456789abcdef" for character in compact)


def is_default_device_name(name):
    cleaned = (name or "").strip().lower()
    return (
        not cleaned
        or cleaned == DEFAULT_DEVICE_NAME.lower()
        or cleaned.startswith("unknown device")
        or cleaned.startswith("private device")
        or is_mac_address_text(cleaned)
    )


def is_default_device_icon(icon):
    return (icon or "").strip().lower() in DEFAULT_DEVICE_ICONS


def guess_device_rule(hostname="", vendor="", open_ports=None):
    text = guess_text(hostname, vendor_display_name(vendor), vendor)
    ports = open_port_numbers(open_ports)
    for rule in DEVICE_GUESS_RULES:
        if any(keyword in text for keyword in rule.get("keywords", ())):
            return rule
        if ports and ports.intersection(rule.get("ports", ())):
            return rule
    return None


def guess_device_icon(hostname="", vendor="", open_ports=None):
    rule = guess_device_rule(hostname=hostname, vendor=vendor, open_ports=open_ports)
    return rule["icon"] if rule else "unknown"


def guess_device_name(hostname, vendor, mac):
    if hostname and not is_default_device_name(hostname):
        return hostname
    if vendor:
        return vendor_display_name(vendor)
    suffix = mac_suffix(mac)
    if suffix and is_locally_administered_mac(mac):
        return f"Private Device {suffix}"
    if suffix:
        return f"Unknown Device {suffix}"
    return DEFAULT_DEVICE_NAME


def guess_device_identity(hostname="", vendor="", mac="", open_ports=None):
    return {
        "name": guess_device_name(hostname, vendor, mac),
        "icon": guess_device_icon(hostname=hostname, vendor=vendor, open_ports=open_ports),
    }


def get_service_name(port, protocol="tcp"):
    try:
        return socket.getservbyport(port, protocol)
    except OSError:
        return ""


def validate_ip_range(ip_range):
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
    except ValueError as exc:
        raise ValueError("IP range must be a valid CIDR range or IP address.") from exc

    if network.version != 4:
        raise ValueError("Only IPv4 ranges are supported.")

    if network.num_addresses > settings.SCAN_MAX_HOSTS:
        raise ValueError(
            f"IP range is too large. Maximum allowed hosts: {settings.SCAN_MAX_HOSTS}."
        )

    is_allowed_private_range = (
        network.is_private or network.is_loopback or network.is_link_local
    )
    if not settings.SCAN_ALLOW_PUBLIC_RANGES and not is_allowed_private_range:
        raise ValueError("Public IP ranges are disabled.")

    return network.with_prefixlen


def default_gateway_from_proc_route(path="/proc/net/route"):
    try:
        with open(path, encoding="utf-8") as route_file:
            next(route_file, None)
            for line in route_file:
                fields = line.strip().split()
                if len(fields) < 3:
                    continue
                destination, gateway = fields[1], fields[2]
                if destination != "00000000" or gateway == "00000000":
                    continue
                return socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
    except (FileNotFoundError, OSError, ValueError):
        return ""
    return ""


def get_default_gateway_ip():
    return default_gateway_from_proc_route()


def clear_stale_gateways(gateway_ip):
    if not gateway_ip:
        return 0
    return Device.objects.filter(is_gateway=True).exclude(ip=gateway_ip).update(is_gateway=False)


def normalize_scan_ports(ports=None):
    ports = ports or settings.PORT_SCAN_PORTS
    normalized_ports = []

    for port in ports:
        try:
            normalized_port = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError("Port scan list must contain only integers.") from exc

        if normalized_port < 1 or normalized_port > 65535:
            raise ValueError("Port scan list must contain values from 1 to 65535.")
        if normalized_port not in normalized_ports:
            normalized_ports.append(normalized_port)

    if len(normalized_ports) > settings.PORT_SCAN_MAX_PORTS:
        raise ValueError(
            f"Too many ports configured. Maximum allowed ports: {settings.PORT_SCAN_MAX_PORTS}."
        )

    return normalized_ports


def scan_open_ports(ip, ports=None, timeout=None):
    ports = normalize_scan_ports(ports)
    timeout = timeout or settings.PORT_SCAN_TIMEOUT
    open_ports = []

    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, int(port)))
            if result == 0:
                open_ports.append(
                    {
                        "port": int(port),
                        "protocol": "tcp",
                        "service": get_service_name(int(port)),
                    }
                )

    return open_ports


def should_scan_ports(device, now=None):
    if not settings.PORT_SCAN_ENABLED:
        return False

    interval = settings.PORT_SCAN_INTERVAL
    if interval <= 0 or not device.last_port_scan:
        return True

    now = now or timezone.now()
    elapsed = now - device.last_port_scan
    return elapsed.total_seconds() >= interval * 60


def should_confirm_offline_with_ports():
    return settings.PORT_SCAN_ENABLED and settings.SCAN_CONFIRM_OFFLINE_WITH_PORTS


def should_confirm_offline_with_icmp():
    return settings.SCAN_CONFIRM_OFFLINE_WITH_ICMP


def status_reason(source, detail=""):
    labels = {
        Device.StatusSource.ARP: "Responded to ARP discovery",
        Device.StatusSource.PORT: "Responded on open ports",
        Device.StatusSource.ICMP: "Responded to ICMP ping",
        Device.StatusSource.RECENT: "Recently seen during scan grace period",
        Device.StatusSource.NONE: "No discovery signal responded",
    }
    reason = labels.get(source, "")
    if detail:
        return f"{reason}: {detail}" if reason else detail
    return reason


def set_device_status(device, status_value, source, reason="", now=None):
    now = now or timezone.now()
    device.status = status_value
    device.status_source = source
    device.status_reason = reason or status_reason(source)
    device.last_status_check = now


def is_mobile_device(device):
    return device.icon in {"phone", "tablet", "smart-watch"}


def is_sleeping_device(device):
    return device.icon in {
        "blinds",
        "ceiling-light",
        "desk-lamp",
        "led-strip",
        "light",
        "shutter",
        "thermostat",
    }


def offline_miss_limit(device):
    if is_mobile_device(device):
        return settings.SCAN_MOBILE_OFFLINE_AFTER_MISSES
    if is_sleeping_device(device):
        return settings.SCAN_SLEEPING_OFFLINE_AFTER_MISSES
    return settings.SCAN_OFFLINE_AFTER_MISSES


def offline_confirmation_ports(device):
    configured_ports = normalize_scan_ports()
    known_open_ports = list(
        device.ports.filter(open=True)
        .order_by("port")
        .values_list("port", flat=True)
    )
    confirmation_ports = []

    for port in configured_ports + known_open_ports:
        if port in confirmation_ports:
            continue
        if len(confirmation_ports) >= settings.PORT_SCAN_MAX_PORTS:
            break
        confirmation_ports.append(port)

    return confirmation_ports


def icmp_responds(ip):
    if not should_confirm_offline_with_icmp():
        return False

    try:
        packet = scapy.IP(dst=ip) / scapy.ICMP()
        return scapy.sr1(packet, timeout=settings.SCAN_ICMP_TIMEOUT, verbose=False) is not None
    except Exception as exc:
        LOGGER.debug("ICMP confirmation failed for %s: %s", ip, exc)
        return False


def keep_online_if_ports_respond(device, scan_run=None, now=None):
    if not should_confirm_offline_with_ports():
        return False

    now = now or timezone.now()
    try:
        open_ports = scan_open_ports(device.ip, ports=offline_confirmation_ports(device))
    except OSError as exc:
        LOGGER.debug("Port confirmation failed for %s: %s", device.ip, exc)
        return False

    device.last_port_scan = now
    if not open_ports:
        device.save(update_fields=["last_port_scan"])
        return False

    device.online = True
    device.missed_scans = 0
    device.lastseen = now
    port_list = ", ".join(f"tcp/{port['port']}" for port in open_ports)
    set_device_status(
        device,
        Device.Status.ONLINE,
        Device.StatusSource.PORT,
        status_reason(Device.StatusSource.PORT, port_list),
        now=now,
    )
    device.save(
        update_fields=[
            "online",
            "missed_scans",
            "lastseen",
            "last_port_scan",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
    )
    sync_device_ports(device, open_ports, scan_run=scan_run)
    return True


def keep_online_if_icmp_responds(device, now=None):
    now = now or timezone.now()
    if not icmp_responds(device.ip):
        return False

    device.online = True
    device.missed_scans = 0
    device.lastseen = now
    set_device_status(
        device,
        Device.Status.ONLINE,
        Device.StatusSource.ICMP,
        now=now,
    )
    device.save(
        update_fields=[
            "online",
            "missed_scans",
            "lastseen",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
    )
    return True


def create_event(event_type, device, message, scan_run=None, device_port=None, metadata=None):
    metadata = metadata or {}
    event = NetworkEvent.objects.create(
        scan_run=scan_run,
        device=device,
        device_port=device_port,
        event_type=event_type,
        message=message,
        metadata=metadata,
    )
    if device.known:
        event.notified = True
        event.metadata = {
            **metadata,
            "notification_skipped": "known_device",
        }
        event.save(update_fields=["notified", "metadata"])
    else:
        notify_event(event)
    return event


def sync_device_ports(device, open_ports, scan_run=None):
    now = timezone.now()
    seen_ports = set()
    ports_opened = 0
    ports_closed = 0

    for port_data in open_ports:
        port = int(port_data["port"])
        protocol = port_data.get("protocol", "tcp")
        service = port_data.get("service", "")
        seen_ports.add((port, protocol))

        device_port, created = DevicePort.objects.get_or_create(
            device=device,
            port=port,
            protocol=protocol,
            defaults={
                "service": service,
                "open": True,
                "firstseen": now,
                "lastseen": now,
            },
        )
        was_open = device_port.open
        device_port.service = service
        device_port.open = True
        device_port.lastseen = now
        device_port.save(update_fields=["service", "open", "lastseen"])

        if created or not was_open:
            ports_opened += 1
            create_event(
                NetworkEvent.EventType.PORT_OPENED,
                device=device,
                device_port=device_port,
                scan_run=scan_run,
                message=f"{device.name} opened {protocol}/{port}",
                metadata={
                    "port": port,
                    "protocol": protocol,
                    "service": service,
                },
            )

    for device_port in device.ports.filter(open=True):
        key = (device_port.port, device_port.protocol)
        if key not in seen_ports:
            device_port.open = False
            device_port.lastseen = now
            device_port.save(update_fields=["open", "lastseen"])
            ports_closed += 1
            create_event(
                NetworkEvent.EventType.PORT_CLOSED,
                device=device,
                device_port=device_port,
                scan_run=scan_run,
                message=f"{device.name} closed {device_port.protocol}/{device_port.port}",
                metadata={
                    "port": device_port.port,
                    "protocol": device_port.protocol,
                    "service": device_port.service,
                },
            )

    return {
        "ports_opened": ports_opened,
        "ports_closed": ports_closed,
    }


def discover_devices(ip_range):
    ip_range = validate_ip_range(ip_range)
    discovered = {}

    for _ in range(max(1, settings.SCAN_ARP_RETRIES)):
        arp_request = scapy.ARP(pdst=ip_range)
        broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered = scapy.srp(
            arp_request_broadcast,
            timeout=settings.SCAN_ARP_TIMEOUT,
            verbose=False,
        )[0]

        for element in answered:
            mac = element[1].hwsrc.lower()
            discovered[mac] = element

    return list(discovered.values())


def scan(ip_range, scan_run=None):
    ip_range = validate_ip_range(ip_range)
    scan_run = scan_run or ScanRun.objects.create(ip_range=ip_range)
    gateway_ip = get_default_gateway_ip()
    ports_opened = 0
    ports_closed = 0
    new_devices = 0

    try:
        answered_list = discover_devices(ip_range)
        scan_started_at = timezone.now()
        oui = scapy.MANUFDB
        hostname_hints = discover_hostname_hints()

        for element in answered_list:
            stats = sync_discovered_device(
                element,
                oui=oui,
                scan_run=scan_run,
                scan_started_at=scan_started_at,
                gateway_ip=gateway_ip,
                hostname_hints=hostname_hints,
            )
            new_devices += stats["new_devices"]
            ports_opened += stats["ports_opened"]
            ports_closed += stats["ports_closed"]

        online_macs = [element[1].hwsrc.lower() for element in answered_list]
        clear_stale_gateways(gateway_ip)
        mark_missing_devices_offline(online_macs, scan_run=scan_run)
    except Exception as exc:
        scan_run.status = ScanRun.Status.FAILED
        scan_run.finished_at = timezone.now()
        scan_run.error = str(exc)
        scan_run.save(update_fields=["status", "finished_at", "error"])
        raise

    scan_run.status = ScanRun.Status.SUCCESS
    scan_run.finished_at = timezone.now()
    scan_run.devices_seen = len(answered_list)
    scan_run.new_devices = new_devices
    scan_run.online_devices = Device.objects.filter(online=True).count()
    scan_run.ports_opened = ports_opened
    scan_run.ports_closed = ports_closed
    scan_run.error = ""
    scan_run.save(
        update_fields=[
            "status",
            "finished_at",
            "devices_seen",
            "new_devices",
            "online_devices",
            "ports_opened",
            "ports_closed",
            "error",
        ]
    )
    return scan_run


def sync_discovered_device(
    element,
    oui=None,
    scan_run=None,
    scan_started_at=None,
    gateway_ip="",
    hostname_hints=None,
):
    scan_started_at = scan_started_at or timezone.now()
    ip = element[1].psrc
    mac = element[1].hwsrc.lower()
    vendor = ManufDA.lookup(oui, mac) if oui else None
    vendor_name = manuf_vendor(mac) or (vendor[1] if vendor else "")
    hostname = get_hostname(ip=ip, hostname_hints=hostname_hints)
    ports_opened = 0
    ports_closed = 0
    new_devices = 0
    is_gateway = bool(gateway_ip and ip == gateway_ip)

    try:
        device = Device.objects.get(mac=mac)
        was_online = device.online
        update_fields = [
            "ip",
            "online",
            "lastseen",
            "missed_scans",
            "status",
            "status_source",
            "status_reason",
            "last_status_check",
        ]
        device.ip = ip
        device.online = True
        device.lastseen = scan_started_at
        device.missed_scans = 0
        resolved_hostname = hostname[:255] if hostname else ""
        if device.hostname != resolved_hostname:
            device.hostname = resolved_hostname
            update_fields.append("hostname")
        resolved_vendor = preferred_vendor(
            observed_vendor=vendor_name,
        )
        if resolved_vendor != device.vendor:
            device.vendor = resolved_vendor
            update_fields.append("vendor")
        if is_gateway and device.role != "gateway":
            device.role = "gateway"
            update_fields.append("role")
        set_device_status(
            device,
            Device.Status.ONLINE,
            Device.StatusSource.ARP,
            now=scan_started_at,
        )
        if is_default_device_name(device.name) or is_default_device_icon(device.icon):
            identity = guess_device_identity(hostname, resolved_vendor, mac)
            if is_default_device_name(device.name):
                device.name = identity["name"]
                update_fields.append("name")
            if is_default_device_icon(device.icon):
                device.icon = identity["icon"]
                update_fields.append("icon")
        if is_gateway:
            device.is_gateway = True
            device.known = True
            if is_default_device_name(device.name):
                device.name = "Gateway"
            device.icon = "router"
            update_fields.extend(["is_gateway", "known", "name", "icon"])
        device.save(update_fields=update_fields)

        if not was_online:
            create_event(
                NetworkEvent.EventType.DEVICE_ONLINE,
                device=device,
                scan_run=scan_run,
                message=f"{device.name} came online",
            )
    except Device.DoesNotExist:
        resolved_vendor = preferred_vendor(
            observed_vendor=vendor_name,
        )
        identity = guess_device_identity(hostname, resolved_vendor, mac)
        if is_gateway:
            identity = {
                "name": "Gateway" if is_default_device_name(identity["name"]) else identity["name"],
                "icon": "router",
            }
        device = Device.objects.create(
            icon=identity["icon"],
            name=identity["name"],
            ip=ip,
            mac=mac,
            vendor=resolved_vendor,
            hostname=hostname[:255] if hostname else "",
            role="gateway" if is_gateway else "device",
            known=is_gateway,
            is_gateway=is_gateway,
            lastseen=scan_started_at,
        )
        set_device_status(
            device,
            Device.Status.ONLINE,
            Device.StatusSource.ARP,
            now=scan_started_at,
        )
        device.save(update_fields=["status", "status_source", "status_reason", "last_status_check"])
        new_devices = 1
        LOGGER.info(
            "Create new device - Mac address: %s / IP: %s / Vendor: %s",
            mac,
            ip,
            device.vendor,
        )
        create_event(
            NetworkEvent.EventType.NEW_DEVICE,
            device=device,
            scan_run=scan_run,
            message=f"Found new device {device.name} at {device.ip}",
            metadata={
                "ip": device.ip,
                "mac": device.mac,
                "vendor": device.vendor,
            },
        )

    if should_scan_ports(device, now=scan_started_at):
        open_ports = scan_open_ports(ip)
        if is_default_device_icon(device.icon):
            device.icon = guess_device_icon(
                hostname=device.name,
                vendor=device.vendor,
                open_ports=open_ports,
            )
            device.save(update_fields=["icon"])
        port_stats = sync_device_ports(device, open_ports, scan_run=scan_run)
        ports_opened += port_stats["ports_opened"]
        ports_closed += port_stats["ports_closed"]
        device.last_port_scan = scan_started_at
        device.save(update_fields=["last_port_scan"])

    return {
        "new_devices": new_devices,
        "ports_opened": ports_opened,
        "ports_closed": ports_closed,
    }


def mark_missing_devices_offline(online_macs, scan_run=None):
    offline_devices = Device.objects.exclude(mac__in=online_macs).filter(online=True)
    for device in offline_devices:
        now = timezone.now()
        device.missed_scans += 1
        miss_limit = offline_miss_limit(device)
        if device.missed_scans < miss_limit:
            status_value = (
                Device.Status.SLEEPING
                if is_sleeping_device(device)
                else Device.Status.RECENTLY_SEEN
            )
            set_device_status(
                device,
                status_value,
                Device.StatusSource.RECENT,
                f"Missed {device.missed_scans}/{miss_limit} scans; keeping device in grace period.",
                now=now,
            )
            device.save(
                update_fields=[
                    "missed_scans",
                    "status",
                    "status_source",
                    "status_reason",
                    "last_status_check",
                ]
            )
            continue

        if keep_online_if_ports_respond(device, scan_run=scan_run, now=now):
            continue

        if keep_online_if_icmp_responds(device, now=now):
            continue

        device.online = False
        set_device_status(
            device,
            Device.Status.OFFLINE,
            Device.StatusSource.NONE,
            f"No discovery signal after {device.missed_scans} missed scans.",
            now=now,
        )
        device.save(
            update_fields=[
                "online",
                "missed_scans",
                "status",
                "status_source",
                "status_reason",
                "last_status_check",
            ]
        )
        create_event(
            NetworkEvent.EventType.DEVICE_OFFLINE,
            device=device,
            scan_run=scan_run,
            message=f"{device.name} went offline",
        )
