import ipaddress
import socket
import struct

from django.conf import settings
import scapy.all as scapy

from .ranges import validate_ip_range


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


def local_scanner_interface(ip_range, route_target=""):
    network = ipaddress.ip_network(validate_ip_range(ip_range), strict=False)
    target = route_target
    if not target or ipaddress.ip_address(target) not in network:
        target = str(next(network.hosts(), network.network_address))

    try:
        interface, source_ip, _ = scapy.conf.route.route(target)
        source_address = ipaddress.ip_address(source_ip)
        if source_address.is_loopback or source_address not in network:
            return None

        mac = scapy.get_if_hwaddr(interface).lower()
        mac_bytes = bytes.fromhex(mac.replace(":", ""))
        if len(mac_bytes) != 6 or not any(mac_bytes) or mac_bytes[0] & 1:
            return None
    except (AttributeError, OSError, TypeError, ValueError):
        return None

    return {"ip": str(source_address), "mac": mac}


def discover_devices(ip_range):
    ip_range = validate_ip_range(ip_range)
    network = ipaddress.ip_network(ip_range, strict=False)
    route_target = str(next(network.hosts(), network.network_address))
    interface = scapy.conf.route.route(route_target)[0]
    discovered = {}

    for _ in range(max(1, settings.SCAN_ARP_RETRIES)):
        arp_request = scapy.ARP(pdst=ip_range)
        broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered = scapy.srp(
            arp_request_broadcast,
            iface=interface,
            timeout=settings.SCAN_ARP_TIMEOUT,
            verbose=False,
        )[0]

        for element in answered:
            mac = element[1].hwsrc.lower()
            discovered[mac] = element

    return list(discovered.values())
