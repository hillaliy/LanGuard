"""Durable, idempotent map mutations; reuse the same validated mutation handlers."""

import re
import logging
from contextvars import ContextVar
from types import SimpleNamespace

from django.db import transaction, OperationalError
from django.utils import timezone
from rest_framework.exceptions import APIException

from .access_control import user_capabilities
from .database_writes import DatabaseWriteBusy, serialized_database_write, sqlite_busy_timeout, sqlite_busy
from .models import NetworkMapCommand

executing_command = ContextVar("executing_map_command", default=False)
HANDLERS = {}
ROUTES = [
    (r"links/", {"POST"}, "network_links"),
    (r"links/bulk/", {"POST"}, "network_links_bulk"),
    (r"links/(?P<link_id>[1-9][0-9]*)/", {"PUT", "DELETE"}, "network_link"),
    (r"layout/", {"PUT"}, "network_layout"),
    (r"internet/", {"PUT", "DELETE"}, "network_internet"),
    (r"suggestions/(?P<key>[a-f0-9]{64})/accept/", {"POST"}, "accept_network_suggestion"),
    (r"suggestions/(?P<key>[a-f0-9]{64})/dismiss/", {"POST"}, "dismiss_network_suggestion"),
    (r"suggestions/restored/", {"DELETE"}, "restore_network_suggestions"),
]


def command_handler(function):
    HANDLERS[function.__name__] = function
    return function


def resolve_command(path, method):
    for pattern, methods, handler in ROUTES:
        match = re.fullmatch(pattern, path)
        if match and method in methods:
            return handler, match.groupdict()
    return None, {}


def command_allowed(user, path):
    return bool(user and user.is_active and user_capabilities(user)[
        "can_edit_home_map" if path == "layout/" else "can_edit_devices"])


def command_data(job, *, include_body=True):
    response = job.result.get("response", {})
    def message(value):
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return "; ".join(filter(None, (message(item) for item in value.values())))
        if isinstance(value, (list, tuple)):
            return "; ".join(filter(None, (message(item) for item in value)))
        return ""
    error = message(response.get("detail", response))[:500] if job.status == "failed" else ""
    pending_interfaces = set()
    if job.status == "queued" and job.method == "POST":
        bodies = [job.body] if job.path == "links/" else job.body.get("connections", []) if job.path == "links/bulk/" else []
        if isinstance(bodies, list):
            for body in bodies[:200]:
                if isinstance(body, dict):
                    for side in ("source", "target"):
                        value = body.get(side)
                        if type(value) is int and value > 0:
                            pending_interfaces.add(value)
    return {"id": job.pk, "request_id": str(job.request_id), "path": job.path,
            "status": job.status, "method": job.method, "body": job.body if include_body else {},
            "result": job.result, "created_at": job.created_at,
            "finished_at": job.finished_at, "error": error, "pending_interfaces": sorted(pending_interfaces)}


def process_next_network_map_command():
    # Import registers the handlers also in the standalone scheduler process.
    from .views import network_map as _views  # noqa: F401

    try:
        with sqlite_busy_timeout(500):
            if not NetworkMapCommand.objects.filter(status="queued").exists():
                return None
        with serialized_database_write(timeout=0.05), sqlite_busy_timeout(500), transaction.atomic():
            job = NetworkMapCommand.objects.select_for_update().filter(status="queued").select_related("requested_by").first()
            if not job:
                return None
            token = executing_command.set(True)
            try:
                try:
                    with transaction.atomic():
                        if not command_allowed(job.requested_by, job.path):
                            from rest_framework.exceptions import PermissionDenied
                            raise PermissionDenied("You no longer have permission to apply this change.")
                        handler, kwargs = resolve_command(job.path, job.method)
                        request = SimpleNamespace(user=job.requested_by, data=job.body, method=job.method)
                        response = HANDLERS[handler](request, **kwargs)
                        result = response.data
                        status = response.status_code
                        if status >= 400:
                            transaction.set_rollback(True)
                except APIException as exc:
                    result, status = {"detail": exc.detail}, exc.status_code
                except Exception as exc:
                    from django.http import Http404
                    if isinstance(exc, OperationalError):
                        raise
                    if isinstance(exc, Http404):
                        result, status = {"detail": "The item no longer exists."}, 404
                    else:
                        logging.getLogger(__name__).exception("Map command %s failed", job.pk)
                        result, status = {"detail": "This change could not be applied. No partial changes were saved."}, 500
                job.status = "succeeded" if status < 400 else "failed"
                job.result = {"status_code": status, "response": result if status >= 400 else {}}
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "result", "finished_at"])
                return job
            finally:
                executing_command.reset(token)
    except DatabaseWriteBusy:
        return None
    except OperationalError as exc:
        if sqlite_busy(exc):
            return None
        raise
