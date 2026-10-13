from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .datetime_utils import utc_isoformat
from .models import SchedulerRuntimeState


def start_scheduler_runtime(now=None):
    timestamp = now or timezone.now()
    state, _ = SchedulerRuntimeState.objects.update_or_create(
        singleton_key=1,
        defaults={
            "heartbeat_at": timestamp,
            "next_scan_at": None,
            "stopped_at": None,
        },
    )
    return state


def touch_scheduler_runtime(now=None):
    timestamp = now or timezone.now()
    updated = SchedulerRuntimeState.objects.filter(singleton_key=1).update(
        heartbeat_at=timestamp,
        stopped_at=None,
        updated_at=timestamp,
    )
    if not updated:
        start_scheduler_runtime(timestamp)


def set_next_scheduled_scan(next_scan_at, now=None):
    timestamp = now or timezone.now()
    SchedulerRuntimeState.objects.update_or_create(
        singleton_key=1,
        defaults={
            "heartbeat_at": timestamp,
            "next_scan_at": next_scan_at,
            "stopped_at": None,
        },
    )


def stop_scheduler_runtime(now=None):
    timestamp = now or timezone.now()
    SchedulerRuntimeState.objects.update_or_create(
        singleton_key=1,
        defaults={
            "heartbeat_at": timestamp,
            "next_scan_at": None,
            "stopped_at": timestamp,
        },
    )


def scheduler_runtime_payload(*, scheduled_scan_running=False, now=None):
    timestamp = now or timezone.now()
    state = SchedulerRuntimeState.objects.filter(singleton_key=1).first()
    stale_after = timedelta(
        seconds=max(1, settings.SCHEDULER_HEARTBEAT_STALE_SECONDS)
    )
    available = bool(
        state
        and state.stopped_at is None
        and state.heartbeat_at
        and state.heartbeat_at >= timestamp - stale_after
    )
    next_scan_at = state.next_scan_at if available and state else None

    if available and scheduled_scan_running:
        runtime_status = "scanning"
        next_scan_at = None
    elif available and next_scan_at:
        runtime_status = "scheduled"
    else:
        runtime_status = "unavailable"
        next_scan_at = None

    return {
        "available": available,
        "status": runtime_status,
        "heartbeat_at": utc_isoformat(state.heartbeat_at) if state else None,
        "next_scan_at": utc_isoformat(next_scan_at),
    }
