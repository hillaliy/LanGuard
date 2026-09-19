import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import DetailedPortScan, Device
from .scan import scan_open_ports, sync_device_ports


LOGGER = logging.getLogger(__name__)
OFFLINE_DEVICE_ERROR = (
    "The device is no longer online. Its saved port inventory was not updated."
)


def parse_port_specification(value, max_ports=None):
    max_ports = max_ports or settings.DETAILED_PORT_SCAN_MAX_PORTS
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a TCP port range or comma-separated list.")

    ports = []
    seen = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            raise ValueError("Port entries cannot be empty.")
        if "-" in token:
            bounds = token.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid port range: {token}.")
            try:
                start, end = (int(bound.strip()) for bound in bounds)
            except ValueError as exc:
                raise ValueError(f"Invalid port range: {token}.") from exc
            if start > end:
                raise ValueError(f"Port range must start before it ends: {token}.")
            candidates = range(start, end + 1)
        else:
            try:
                candidates = (int(token),)
            except ValueError as exc:
                raise ValueError(f"Invalid TCP port: {token}.") from exc

        for port in candidates:
            if port < 1 or port > 65535:
                raise ValueError("TCP ports must be between 1 and 65535.")
            if port in seen:
                continue
            seen.add(port)
            ports.append(port)
            if len(ports) > max_ports:
                raise ValueError(f"A detailed scan can include at most {max_ports} ports.")

    return ports


def recover_interrupted_detailed_port_scans():
    now = timezone.now()
    return DetailedPortScan.objects.filter(
        status=DetailedPortScan.Status.RUNNING,
    ).update(
        status=DetailedPortScan.Status.FAILED,
        finished_at=now,
        error="The scan was interrupted when the scheduler stopped.",
    )


def claim_next_detailed_port_scan():
    with transaction.atomic():
        job = (
            DetailedPortScan.objects.select_for_update()
            .filter(status=DetailedPortScan.Status.QUEUED)
            .order_by("created_at")
            .first()
        )
        if not job:
            return None
        job.status = DetailedPortScan.Status.RUNNING
        job.started_at = timezone.now()
        job.error = ""
        job.save(update_fields=["status", "started_at", "error"])
        return job


def finish_cancelled_scan(job):
    job.status = DetailedPortScan.Status.CANCELLED
    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "scanned_ports",
            "open_ports",
            "finished_at",
        ]
    )
    return job


def fail_offline_scan(job):
    job.status = DetailedPortScan.Status.FAILED
    job.finished_at = timezone.now()
    job.error = OFFLINE_DEVICE_ERROR
    job.save(update_fields=["status", "finished_at", "error"])
    return job


def scan_device_is_online(job):
    job.device.refresh_from_db(fields=["status"])
    return job.device.status == Device.Status.ONLINE


def run_detailed_port_scan(job):
    if not scan_device_is_online(job):
        return fail_offline_scan(job)

    deadline = time.monotonic() + settings.DETAILED_PORT_SCAN_MAX_SECONDS
    open_ports = []

    try:
        for index, port in enumerate(job.ports, start=1):
            job.refresh_from_db(fields=["cancel_requested"])
            if job.cancel_requested:
                return finish_cancelled_scan(job)
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"The detailed scan exceeded the {settings.DETAILED_PORT_SCAN_MAX_SECONDS}-second limit."
                )

            open_ports.extend(
                scan_open_ports(
                    job.device.ip,
                    ports=[port],
                    timeout=settings.DETAILED_PORT_SCAN_TIMEOUT,
                )
            )
            job.scanned_ports = index
            job.open_ports = open_ports
            if index == job.total_ports or index % 5 == 0:
                job.save(update_fields=["scanned_ports", "open_ports"])

        job.refresh_from_db(fields=["cancel_requested"])
        if job.cancel_requested:
            return finish_cancelled_scan(job)
        if not scan_device_is_online(job):
            return fail_offline_scan(job)

        stats = sync_device_ports(
            job.device,
            open_ports,
            scanned_ports=job.ports,
        )
        job.device.last_port_scan = timezone.now()
        job.device.save(update_fields=["last_port_scan"])
        job.status = DetailedPortScan.Status.SUCCESS
        job.finished_at = timezone.now()
        job.error = ""
        job.save(
            update_fields=[
                "status",
                "scanned_ports",
                "open_ports",
                "finished_at",
                "error",
            ]
        )
        LOGGER.info(
            "Detailed port scan %s completed for device %s: %s open, %s closed",
            job.id,
            job.device_id,
            stats["ports_opened"],
            stats["ports_closed"],
        )
    except TimeoutError as exc:
        LOGGER.warning("Detailed port scan %s timed out", job.id)
        job.status = DetailedPortScan.Status.FAILED
        job.finished_at = timezone.now()
        job.error = str(exc)
        job.save(
            update_fields=[
                "status",
                "scanned_ports",
                "open_ports",
                "finished_at",
                "error",
            ]
        )
    except Exception:
        LOGGER.exception("Detailed port scan %s failed", job.id)
        job.status = DetailedPortScan.Status.FAILED
        job.finished_at = timezone.now()
        job.error = "The detailed port scan failed. Check the scheduler logs."
        job.save(
            update_fields=[
                "status",
                "scanned_ports",
                "open_ports",
                "finished_at",
                "error",
            ]
        )
    return job


def process_next_detailed_port_scan():
    job = claim_next_detailed_port_scan()
    return run_detailed_port_scan(job) if job else None
