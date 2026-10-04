import ipaddress
import re

from django.conf import settings


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


def validate_ip_ranges(ip_ranges):
    if isinstance(ip_ranges, str):
        values = [value for value in re.split(r"[,\n]+", ip_ranges) if value.strip()]
    elif isinstance(ip_ranges, (list, tuple)):
        values = list(ip_ranges)
    else:
        raise ValueError("Network ranges must be provided as a list of CIDR ranges.")

    if not values:
        raise ValueError("Configure at least one network range.")
    if len(values) > settings.SCAN_MAX_RANGES:
        raise ValueError(
            f"Too many network ranges. Maximum allowed ranges: {settings.SCAN_MAX_RANGES}."
        )

    normalized = []
    networks = []
    for value in values:
        network_range = validate_ip_range(str(value).strip())
        network = ipaddress.ip_network(network_range, strict=False)
        if any(network.overlaps(existing) for existing in networks):
            raise ValueError(
                "Network ranges must not overlap. CIDR entries are normalized to "
                "their network boundary; use one larger range instead of adding "
                "ranges it already contains."
            )
        normalized.append(network_range)
        networks.append(network)
    return normalized
