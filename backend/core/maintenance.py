from datetime import timedelta

from django.utils import timezone

from .datetime_utils import utc_isoformat
from .models import (
    AdGuardUnmatchedClient,
    DeviceDNSActivity,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)


ACTIVITY_CLEANUP_TARGETS = {"events", "scan_runs", "notifications", "dns_activity"}


def cleanup_activity(target, older_than_days=90, clean_all=False):
    target = str(target or "").strip()
    if target not in ACTIVITY_CLEANUP_TARGETS:
        raise ValueError("target")

    if clean_all:
        older_than_days = None
        cutoff = None
    else:
        older_than_days = int(older_than_days)
        if older_than_days < 1 or older_than_days > 3650:
            raise ValueError("older_than_days")
        cutoff = timezone.now() - timedelta(days=older_than_days)

    deleted = {
        "notifications": 0,
        "events": 0,
        "scan_runs": 0,
        "dns_activity": 0,
        "dns_unmatched_clients": 0,
    }

    if target == "notifications":
        queryset = NotificationDelivery.objects.all()
        if cutoff is not None:
            queryset = queryset.filter(created_at__lt=cutoff)
        deleted["notifications"], _ = queryset.delete()
    elif target == "events":
        queryset = NetworkEvent.objects.all()
        if cutoff is not None:
            queryset = queryset.filter(created_at__lt=cutoff)
        _, event_details = queryset.delete()
        deleted["events"] = event_details.get("core.NetworkEvent", 0)
        deleted["notifications"] = event_details.get("core.NotificationDelivery", 0)
    elif target == "scan_runs":
        queryset = ScanRun.objects.exclude(status=ScanRun.Status.RUNNING)
        if cutoff is not None:
            queryset = queryset.filter(started_at__lt=cutoff)
        _, scan_run_details = queryset.delete()
        deleted["scan_runs"] = scan_run_details.get("core.ScanRun", 0)
    elif target == "dns_activity":
        activity_queryset = DeviceDNSActivity.objects.all()
        unmatched_queryset = AdGuardUnmatchedClient.objects.all()
        if cutoff is not None:
            activity_queryset = activity_queryset.filter(last_seen__lt=cutoff)
            unmatched_queryset = unmatched_queryset.filter(last_seen__lt=cutoff)
        _, activity_details = activity_queryset.delete()
        _, unmatched_details = unmatched_queryset.delete()
        deleted["dns_activity"] = activity_details.get("core.DeviceDNSActivity", 0)
        deleted["dns_unmatched_clients"] = unmatched_details.get(
            "core.AdGuardUnmatchedClient", 0
        )

    return {
        "target": target,
        "older_than_days": older_than_days,
        "clean_all": clean_all,
        "cutoff": utc_isoformat(cutoff) if cutoff is not None else None,
        "deleted": deleted,
    }


def cleanup_all_activity(older_than_days):
    summary = {
        "older_than_days": int(older_than_days),
        "deleted": {
            "notifications": 0,
            "events": 0,
            "scan_runs": 0,
            "dns_activity": 0,
            "dns_unmatched_clients": 0,
        },
        "targets": {},
    }

    for target in ("notifications", "events", "scan_runs"):
        result = cleanup_activity(target, older_than_days)
        summary["targets"][target] = result
        for key, value in result["deleted"].items():
            summary["deleted"][key] += value

    return summary
