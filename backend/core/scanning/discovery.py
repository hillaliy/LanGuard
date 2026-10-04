import ipaddress
import logging
import random
import re
import socket
import struct
import time
import warnings
from urllib.parse import urlparse

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..models import Device
from .identity import clean_hostname, is_mac_address_text


LOGGER = logging.getLogger(__name__)
SSDP_CACHE_TTL_SECONDS = 10
SSDP_METADATA_CACHE = {"expires_at": 0.0, "metadata": {}}
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

    # The UDP sender may be a cache or proxy for another device's service.
    # Trust names only when an address record links them to an IP; service
    # instance names additionally require an SRV target linked to that address.
    hostnames_by_ip.update(mdns_service_hostnames_from_responses(responses))
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
    return {
        ip: metadata["hostname"]
        for ip, metadata in ssdp_metadata_map().items()
        if metadata.get("hostname")
    }


def ssdp_metadata_map():
    now = time.monotonic()
    if SSDP_METADATA_CACHE["expires_at"] > now:
        return dict(SSDP_METADATA_CACHE["metadata"])

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

    metadata_by_ip = {}
    for response, source_ip in responses:
        metadata = ssdp_metadata_from_response(response, source_ip)
        if not metadata:
            continue
        current = metadata_by_ip.setdefault(source_ip, {})
        for key, value in metadata.items():
            if value and not current.get(key):
                current[key] = value

    SSDP_METADATA_CACHE["expires_at"] = now + SSDP_CACHE_TTL_SECONDS
    SSDP_METADATA_CACHE["metadata"] = metadata_by_ip
    return dict(metadata_by_ip)


def ssdp_hostname_from_response(response, ip):
    return ssdp_metadata_from_response(response, ip).get("hostname", "")


def ssdp_metadata_from_response(response, ip):
    text = response.decode("utf-8", "ignore")
    headers = parse_http_headers(text)
    location = headers.get("location", "")
    if not location:
        return {}
    parsed = urlparse(location)
    if parsed.hostname and parsed.hostname != ip:
        return {}
    try:
        result = requests.get(location, timeout=1.0, headers={"User-Agent": "LanGuard/1.0"})
    except requests.RequestException as exc:
        LOGGER.debug("SSDP device description fetch failed for %s: %s", ip, exc)
        return {}
    body = result.text[:128_000]
    return metadata_from_device_description(body, ip)


def parse_http_headers(text):
    headers = {}
    for line in text.splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def hostname_from_device_description(body, ip=""):
    return metadata_from_device_description(body, ip).get("hostname", "")


def metadata_from_device_description(body, ip=""):
    metadata = {}
    manufacturer = xml_description_value(body, "manufacturer")
    if manufacturer and not is_mac_address_text(manufacturer):
        metadata["vendor"] = manufacturer
    for tag in ("friendlyName", "modelName"):
        hostname = clean_hostname(xml_description_value(body, tag), ip_address=ip)
        if hostname and hostname != ip:
            metadata["hostname"] = hostname
            break
    return metadata


def xml_description_value(body, tag):
    match = re.search(rf"<{tag}>\s*([^<]+)\s*</{tag}>", body or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""


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


def get_hostname(ip, hostname_hints=None, include_source=False, dns_server=""):
    lookup_steps = [
        (Device.IdentitySource.REVERSE_DNS, reverse_dns_hostname),
    ]
    if dns_server:
        lookup_steps.append((
            Device.IdentitySource.REVERSE_DNS,
            lambda address: dns_server_reverse_hostname(address, dns_server),
        ))
    lookup_steps.append((Device.IdentitySource.MDNS, mdns_reverse_hostname))
    if hostname_hints is None:
        lookup_steps.extend((
            (Device.IdentitySource.MDNS, mdns_service_hostname),
            (Device.IdentitySource.LLMNR, llmnr_reverse_hostname),
            (Device.IdentitySource.SSDP, ssdp_hostname),
        ))
    else:
        def hinted_hostname(address):
            hint = hostname_hints.get(address, "")
            return hint[0] if isinstance(hint, tuple) else hint

        lookup_steps.extend((
            ("hint", hinted_hostname),
            (Device.IdentitySource.LLMNR, llmnr_reverse_hostname),
        ))
    lookup_steps.append((Device.IdentitySource.NETBIOS, netbios_hostname))
    for source, lookup in lookup_steps:
        hostname = lookup(ip)
        if hostname:
            if source == "hint":
                hint = hostname_hints.get(ip, "")
                source = hint[1] if isinstance(hint, tuple) else ""
            return (hostname, source) if include_source else hostname
    return ("", "") if include_source else ""


def discover_hostname_hints():
    hints = {
        ip: (hostname, Device.IdentitySource.SSDP)
        for ip, hostname in ssdp_hostname_map().items()
    }
    hints.update({
        ip: (hostname, Device.IdentitySource.MDNS)
        for ip, hostname in mdns_service_hostname_map().items()
    })
    return hints


def reverse_dns_hostname(ip):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return clean_hostname(hostname)
    except (socket.herror, socket.gaierror, TimeoutError, OSError) as e:
        LOGGER.debug("Reverse DNS hostname lookup failed for %s: %s", ip, e)
        return ""


def dns_server_reverse_hostname(ip, dns_server):
    name = reverse_dns_name(ip)
    if not name or not dns_server:
        return ""
    packet = dns_query_packet(name, query_type=12)
    try:
        response = udp_exchange(packet, dns_server, 53, 0.7)
    except OSError as exc:
        LOGGER.debug("Gateway DNS hostname lookup failed for %s via %s: %s", ip, dns_server, exc)
        return ""
    for ptr_name in dns_ptr_names(response, expected_owner=name):
        hostname = clean_hostname(ptr_name, ip_address=ip)
        if hostname:
            return hostname
    return ""
