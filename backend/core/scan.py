from django.utils import timezone
from django.conf import settings

import logging

import scapy.all as scapy
from scapy.data import ManufDA, load_manuf
from onepush import get_notifier

from .models import Device


LOGGER = logging.getLogger(__name__)


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
        mac = element[1].hwsrc
        vendor = ManufDA.lookup(oui, mac)  # Find OUI name matching to a MAC
        try:
            device = Device.objects.get(mac=mac)
            device.ip = ip
            device.online = True
            device.lastseen = timezone.now()
        except Device.DoesNotExist:
            device = Device(
                icon="plus",
                name="device",
                ip=ip,
                mac=mac,
                vendor=vendor[1],
                lastseen=timezone.now(),
            )
            LOGGER.info(
                f"Create new device -  Mac address: {mac} / IP: {ip} / Vendor: {vendor[1]}"
            )

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

        device.save()
    Device.objects.exclude(
        mac__in=[element[1].hwsrc for element in answered_list]
    ).update(online=False)


def one_push(notifier, webhook, content):
    n = get_notifier(notifier)
    title = "LanGuard"
    response = n.notify(webhook=webhook, title=title, content=content)


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
