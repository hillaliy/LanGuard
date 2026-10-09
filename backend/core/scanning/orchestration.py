import logging

from django.conf import settings
from django.utils import timezone
import scapy.all as scapy

from ..models import AppSettings, Device, ScanRun
from ..device_merging import logical_online_device_count
from ..user_messages import scan_error_message
from .discovery import discover_hostname_hints, ssdp_metadata_map
from .lifecycle import claim_scan_run, scan_failure_diagnostics, touch_scan_run
from .network import discover_devices, get_default_gateway_ip, local_scanner_interface
from .presence import clear_stale_gateways, mark_missing_devices_offline
from .ranges import validate_ip_ranges
from .reconciliation import sync_discovered_device
from .snmp import discover_snmp_inventory


LOGGER = logging.getLogger(__name__)


def scan(ip_ranges, *, source=ScanRun.Source.COMMAND):
    scan_ranges = validate_ip_ranges(ip_ranges)
    primary_range = scan_ranges[0]
    config = AppSettings.load()
    configured_labels = config.effective_scan_range_labels
    scan_range_labels = {
        network_range: configured_labels[network_range]
        for network_range in scan_ranges
        if network_range in configured_labels
    }
    scan_run = claim_scan_run(scan_ranges, scan_range_labels, source)
    if (
        scan_run.ip_range != primary_range
        or scan_run.scan_ranges != scan_ranges
        or scan_run.scan_range_labels != scan_range_labels
    ):
        scan_run.ip_range = primary_range
        scan_run.scan_ranges = scan_ranges
        scan_run.scan_range_labels = scan_range_labels
        scan_run.save(update_fields=["ip_range", "scan_ranges", "scan_range_labels"])
    gateway_ip = get_default_gateway_ip()
    ports_opened = 0
    ports_closed = 0
    new_devices = 0

    failure_stage = "scan_setup"
    try:
        touch_scan_run(scan_run)
        discovered = {}
        local_scanner_macs = set()
        for ip_range in scan_ranges:
            failure_stage = "arp_discovery"
            touch_scan_run(scan_run)
            for element in discover_devices(ip_range):
                discovered[element[1].hwsrc.lower()] = element
            touch_scan_run(scan_run)

            local_interface = local_scanner_interface(ip_range, route_target=gateway_ip)
            if local_interface:
                local_scanner_mac = local_interface["mac"]
                local_scanner_macs.add(local_scanner_mac)
                discovered.setdefault(
                    local_scanner_mac,
                    (
                        None,
                        scapy.ARP(
                            psrc=local_interface["ip"],
                            hwsrc=local_scanner_mac,
                        ),
                    ),
                )

        answered_list = list(discovered.values())
        scan_started_at = timezone.now()
        oui = scapy.MANUFDB
        failure_stage = "metadata_discovery"
        hostname_hints = discover_hostname_hints()
        vendor_hints = {
            ip: (metadata["vendor"], Device.IdentitySource.SSDP)
            for ip, metadata in ssdp_metadata_map().items()
            if metadata.get("vendor")
        }
        snmp_hints = {}
        if config.snmp_enabled and config.snmp_community:
            snmp_hints = discover_snmp_inventory(
                [element[1].psrc for element in answered_list],
                config.snmp_community,
                timeout=settings.SNMP_TIMEOUT,
                max_devices=settings.SNMP_MAX_DEVICES,
                max_interfaces=settings.SNMP_MAX_INTERFACES,
                max_neighbors=settings.SNMP_MAX_NEIGHBORS,
                concurrency=settings.SNMP_CONCURRENCY,
            )
            for ip, metadata in snmp_hints.items():
                hostname = metadata.get("system", {}).get("name")
                vendor = metadata.get("vendor")
                if hostname:
                    hostname_hints[ip] = (hostname, Device.IdentitySource.SNMP)
                if vendor:
                    vendor_hints[ip] = (vendor, Device.IdentitySource.SNMP)

        failure_stage = "device_sync"
        for element in answered_list:
            touch_scan_run(scan_run)
            stats = sync_discovered_device(
                element,
                oui=oui,
                scan_run=scan_run,
                scan_started_at=scan_started_at,
                gateway_ip=gateway_ip,
                hostname_hints=hostname_hints,
                vendor_hints=vendor_hints,
                snmp_hints=snmp_hints,
                status_source=(
                    Device.StatusSource.LOCAL
                    if element[1].hwsrc.lower() in local_scanner_macs
                    else Device.StatusSource.ARP
                ),
            )
            new_devices += stats["new_devices"]
            ports_opened += stats["ports_opened"]
            ports_closed += stats["ports_closed"]

        online_macs = [element[1].hwsrc.lower() for element in answered_list]
        failure_stage = "status_reconciliation"
        touch_scan_run(scan_run)
        clear_stale_gateways(gateway_ip)
        mark_missing_devices_offline(
            online_macs,
            scan_run=scan_run,
            ip_ranges=scan_ranges,
        )

        failure_stage = "finalization"
        scan_run.status = ScanRun.Status.SUCCESS
        scan_run.finished_at = timezone.now()
        scan_run.heartbeat_at = scan_run.finished_at
        scan_run.devices_seen = len(answered_list)
        scan_run.new_devices = new_devices
        scan_run.online_devices = logical_online_device_count()
        scan_run.ports_opened = ports_opened
        scan_run.ports_closed = ports_closed
        scan_run.error = ""
        scan_run.failure_code = ""
        scan_run.failure_type = ""
        scan_run.failure_stage = ""
        scan_run.failure_fingerprint = ""
        scan_run.save(
            update_fields=[
                "status",
                "finished_at",
                "heartbeat_at",
                "devices_seen",
                "new_devices",
                "online_devices",
                "ports_opened",
                "ports_closed",
                "error",
                "failure_code",
                "failure_type",
                "failure_stage",
                "failure_fingerprint",
            ]
        )
    except Exception as exc:
        failure = scan_failure_diagnostics(exc, failure_stage)
        finished_at = timezone.now()
        try:
            ScanRun.objects.filter(pk=scan_run.pk).update(
                status=ScanRun.Status.FAILED,
                finished_at=finished_at,
                heartbeat_at=finished_at,
                error=scan_error_message(exc),
                failure_code=failure["code"],
                failure_type=failure["type"],
                failure_stage=failure["stage"],
                failure_fingerprint=failure["fingerprint"],
            )
        except Exception:
            LOGGER.exception("Could not persist network scan failure diagnostics")
        raise
    return scan_run
