import re

from .vendor import is_locally_administered_mac


DEFAULT_DEVICE_NAME = "Device"


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
        "icon": "game-console",
        "keywords": (
            "game console",
            "playstation",
            "xbox",
            "nintendo switch",
        ),
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
        "icon": "nas",
        "keywords": (
            "nas",
            "network attached storage",
            "synology",
            "qnap",
        ),
    },
    {
        "icon": "power-meter",
        "keywords": ("power meter", "energy meter", "smart meter"),
    },
    {
        "icon": "smart-power-strip",
        "keywords": ("smart power strip", "power strip", "multi plug"),
    },
    {
        "icon": "smart-relay",
        "keywords": ("smart relay", "wifi relay", "relay switch"),
    },
    {
        "icon": "server",
        "keywords": ("server",),
        "ports": (22,),
    },
]

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
    vendor = canonical_vendor(observed_vendor)
    return "" if is_mac_address_text(vendor) else vendor


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


def is_default_device_name(name):
    cleaned = (name or "").strip().lower()
    return (
        not cleaned
        or cleaned == DEFAULT_DEVICE_NAME.lower()
        or cleaned.startswith("unknown device")
        or cleaned.startswith("private device")
        or is_mac_address_text(cleaned)
    )


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


def clean_hostname(hostname, ip_address=""):
    hostname = (hostname or "").strip().rstrip(".")
    lowered = hostname.lower()
    short_hostname = hostname.split(".")[0].lstrip("_").strip()
    lowered_short_hostname = short_hostname.lower()
    invalid_values = {"", "?", "in", "internet", "ptr", "a", "aaaa", "_gateway", "gateway"}
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
        lowered_short_hostname in invalid_values
        or short_hostname == ip_address
        or short_hostname.startswith(";")
        or short_hostname.isdigit()
        or any(fragment in lowered for fragment in invalid_fragments)
    ):
        return ""
    return short_hostname.replace("-", " ").strip()


def mismatched_default_haa_hostname(hostname, mac):
    match = re.fullmatch(
        r"HAA[ -]([0-9A-F]{6})(?:[ -](?:Setup|InstallerM|InstallerB))?",
        (hostname or "").strip(),
        re.IGNORECASE,
    )
    if not match:
        return False
    normalized_mac = re.sub(r"[^0-9A-F]", "", mac or "", flags=re.IGNORECASE)
    return len(normalized_mac) != 12 or match.group(1).lower() != normalized_mac[-6:].lower()


def validated_hostname(hostname, mac):
    return "" if mismatched_default_haa_hostname(hostname, mac) else hostname


def is_mac_address_text(value):
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return False
    compact = cleaned.replace(":", "").replace("-", "")
    return len(compact) == 12 and all(character in "0123456789abcdef" for character in compact)
