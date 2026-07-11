from datetime import UTC

from django.utils import timezone


def utc_isoformat(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")
