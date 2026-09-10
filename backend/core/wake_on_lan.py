import ipaddress
import socket


DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"
DEFAULT_PORT = 9
MAGIC_PACKET_REPETITIONS = 3


def magic_packet(mac_address):
    compact = "".join(character for character in str(mac_address) if character.isalnum())
    if len(compact) != 12:
        raise ValueError("The device does not have a valid MAC address.")
    try:
        mac_bytes = bytes.fromhex(compact)
    except ValueError as exc:
        raise ValueError("The device does not have a valid MAC address.") from exc
    return b"\xff" * 6 + mac_bytes * 16


def wake_broadcast_address(device_ip, network_ranges):
    try:
        address = ipaddress.ip_address(device_ip)
    except ValueError as exc:
        raise ValueError("The device does not have a valid IPv4 address.") from exc
    if address.version != 4:
        raise ValueError("Wake-on-LAN currently requires an IPv4 device address.")

    matching_networks = []
    for value in network_ranges:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            continue
        if network.version == 4 and network.prefixlen < 31 and address in network:
            matching_networks.append(network)

    if not matching_networks:
        return DEFAULT_BROADCAST_ADDRESS
    network = max(matching_networks, key=lambda candidate: candidate.prefixlen)
    return str(network.broadcast_address)


def send_magic_packet(mac_address, broadcast_address, port=DEFAULT_PORT):
    packet = magic_packet(mac_address)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wake_socket:
        wake_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _ in range(MAGIC_PACKET_REPETITIONS):
            wake_socket.sendto(packet, (broadcast_address, port))
