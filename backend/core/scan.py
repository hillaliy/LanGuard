from django.utils import timezone
from django.conf import settings
import socket

import logging

import scapy.all as scapy
from scapy.data import ManufDA, load_manuf
from onepush import get_notifier

from .models import Device, DevicePort


LOGGER = logging.getLogger(__name__)


def get_hostname(ip):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except socket.herror as e:
        LOGGER.debug("Hostname lookup failed for %s: %s", ip, e)
        return "Device"


def get_service_name(port, protocol="tcp"):
    try:
        return socket.getservbyport(port, protocol)
    except OSError:
        return ""


def scan_open_ports(ip, ports=None, timeout=None):
    ports = ports or settings.PORT_SCAN_PORTS
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


def sync_device_ports(device, open_ports):
    now = timezone.now()
    seen_ports = set()

    for port_data in open_ports:
        port = port_data["port"]
        protocol = port_data.get("protocol", "tcp")
        seen_ports.add((port, protocol))
        device_port, _ = DevicePort.objects.get_or_create(
            device=device,
            port=port,
            protocol=protocol,
            defaults={
                "service": port_data.get("service", ""),
                "open": True,
                "firstseen": now,
                "lastseen": now,
            },
        )
        device_port.service = port_data.get("service", "")
        device_port.open = True
        device_port.lastseen = now
        device_port.save(update_fields=["service", "open", "lastseen"])

    for device_port in device.ports.filter(open=True):
        key = (device_port.port, device_port.protocol)
        if key not in seen_ports:
            device_port.open = False
            device_port.lastseen = now
            device_port.save(update_fields=["open", "lastseen"])


def scan(IP_RANGE):
    oui = load_manuf(settings.MANUF_FILE)  # Load the local OUI database
    arp_request = scapy.ARP(pdst=IP_RANGE)  # Create an ARP request packet
    broadcast = scapy.Ether(
        dst="ff:ff:ff:ff:ff:ff"
    )  # Create a broadcast Ethernet frame
    arp_request_broadcast = (
        broadcast / arp_request
    )  # Combine the ARP request and broadcast frame into a single packet
    answered_list = scapy.srp(arp_request_broadcast, timeout=1, verbose=False)[
        0
    ]  # Send the packet and capture the response

    for element in answered_list:
        ip = element[1].psrc
        mac = element[1].hwsrc.lower()
        vendor = ManufDA.lookup(oui, mac)  # Find OUI name matching to a MAC
        try:
            device = Device.objects.get(mac=mac)
            device.ip = ip
            device.online = True
            device.lastseen = timezone.now()
        except Device.DoesNotExist:
            name = get_hostname(ip=ip)
            device = Device(
                icon="plus",
                name=name,
                ip=ip,
                mac=mac,
                vendor=vendor[1] if vendor else "",
                lastseen=timezone.now(),
            )
            LOGGER.info(
                "Create new device - Mac address: %s / IP: %s / Vendor: %s",
                mac,
                ip,
                device.vendor,
            )

            notify_new_device(device)

        device.save()

        if settings.PORT_SCAN_ENABLED:
            sync_device_ports(device, scan_open_ports(ip))

    online_macs = [element[1].hwsrc.lower() for element in answered_list]
    Device.objects.exclude(mac__in=online_macs).update(online=False)


def notify_new_device(device):
    if not settings.DISCORD_WEBHOOK:
        return

    one_push(
        notifier="discord",
        webhook=settings.DISCORD_WEBHOOK,
        content=f"""
        Found a new device:
        Mac: {device.mac}
        IP: {device.ip}
        Vendor: {device.vendor}
        Date: {device.lastseen.strftime("%d, %B %Y")}
        Time: {device.lastseen.strftime("%H:%M")}
        """,
    )


def one_push(notifier, webhook, content):
    n = get_notifier(notifier)
    title = "LanGuard"
    return n.notify(webhook=webhook, title=title, content=content)


#     print(n.params)
#     print(response.text)
# **********  OR **************
#     notify('bark', key='YOUR_BARK_KEY', title='OnePush', content='Hello World!')
#
# {'required': ['key'], 'optional': ['title', 'content', 'sound', 'isarchive', 'icon', 'group', 'url', 'copy', 'autocopy']}
# {"code":200,"message":"success","timestamp":1633528319}
# Notifiers: Bark, Discord, Telegram, ServerChan, ServerChanTurbo, WechatWorkApp, WechatWorkBot, pushplus, go-cqhttp, Qmsg, DingTalk, Lark, SMTP

"""
discord - {'required': ['webhook'], 'optional': ['title', 'content', 'username', 'avatar_url', 'color']}

telegram - {'required': ['token', 'userid'], 'optional': ['title', 'content', 'api_url']}

smtp - {'required': ['host', 'user', 'password'], 'optional': ['port', 'ssl', 'msg', 'subject', 'title', 'content', 'From', 'To']}
"""
