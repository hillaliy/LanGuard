import hashlib
import re
import socket
from datetime import timedelta

import requests
from django.conf import settings
from django.db import DatabaseError, IntegrityError, OperationalError, transaction
from django.utils import timezone

from ..models import ScanRun


STALE_SCAN_ERROR = "Scan was interrupted and its stale lock was released."


class ScanAlreadyRunning(RuntimeError):
    def __init__(self, active_scan=None):
        self.active_scan = active_scan
        source = active_scan.get_source_display().lower() if active_scan else "network"
        super().__init__(f"A {source} scan is already running.")


def scan_failure_diagnostics(exc, stage):
    message = str(exc).lower()
    if isinstance(exc, OperationalError) and "locked" in message:
        code = "database_locked"
    elif isinstance(exc, IntegrityError):
        code = "database_integrity"
    elif isinstance(exc, DatabaseError):
        code = "database_error"
    elif isinstance(exc, PermissionError):
        code = "permission_denied"
    elif isinstance(exc, (TimeoutError, socket.timeout)):
        code = "timeout"
    elif isinstance(exc, requests.RequestException):
        code = "external_request"
    elif isinstance(exc, ScanAlreadyRunning):
        code = "scan_lock_lost"
    elif isinstance(exc, OSError):
        code = "network_io"
    else:
        code = "unexpected_error"

    failure_type = re.sub(r"[^A-Za-z0-9_.-]", "_", type(exc).__name__)[:64]
    fingerprint_source = f"{type(exc).__module__}.{type(exc).__qualname__}:{exc}"
    return {
        "code": code,
        "type": failure_type,
        "stage": stage,
        "fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16],
    }


def expire_stale_scan_runs(now=None):
    now = now or timezone.now()
    stale_after = max(60, settings.SCAN_LOCK_STALE_SECONDS)
    cutoff = now - timedelta(seconds=stale_after)
    return ScanRun.objects.filter(
        status=ScanRun.Status.RUNNING,
        heartbeat_at__lt=cutoff,
    ).update(
        status=ScanRun.Status.FAILED,
        finished_at=now,
        error=STALE_SCAN_ERROR,
        failure_code="stale_scan_lock",
        failure_type="InterruptedScan",
        failure_stage="heartbeat",
        failure_fingerprint="stale-scan-lock",
    )


def active_scan_run(now=None):
    expire_stale_scan_runs(now=now)
    return ScanRun.objects.filter(status=ScanRun.Status.RUNNING).first()


def claim_scan_run(scan_ranges, scan_range_labels, source):
    expire_stale_scan_runs()
    try:
        with transaction.atomic():
            return ScanRun.objects.create(
                ip_range=scan_ranges[0],
                scan_ranges=scan_ranges,
                scan_range_labels=scan_range_labels,
                source=source,
            )
    except IntegrityError as exc:
        raise ScanAlreadyRunning(active_scan_run()) from exc


def touch_scan_run(scan_run):
    heartbeat_at = timezone.now()
    updated = ScanRun.objects.filter(
        pk=scan_run.pk,
        status=ScanRun.Status.RUNNING,
    ).update(heartbeat_at=heartbeat_at)
    if not updated:
        raise ScanAlreadyRunning(active_scan_run())
    scan_run.heartbeat_at = heartbeat_at
