from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response


def parse_int_param(params, name, default, minimum=0, maximum=None):
    raw_value = params.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Must be an integer."}) from exc

    if value < minimum:
        raise ValidationError({name: f"Must be greater than or equal to {minimum}."})
    if maximum is not None and value > maximum:
        raise ValidationError({name: f"Must be less than or equal to {maximum}."})
    return value


def parse_bool_param(params, name):
    raw_value = params.get(name)
    if raw_value is None or raw_value == "":
        return None

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError({name: "Must be a boolean value."})


def parse_datetime_param(params, name):
    raw_value = params.get(name)
    if not raw_value:
        return None

    value = parse_datetime(raw_value)
    if value is None:
        raise ValidationError({name: "Must be an ISO 8601 datetime."})
    return value


def paginated_response(request, queryset, serializer_class, default_limit=50, max_limit=200):
    return Response(
        paginated_payload(
            request,
            queryset,
            serializer_class,
            default_limit=default_limit,
            max_limit=max_limit,
        )
    )


def paginated_payload(request, queryset, serializer_class, default_limit=50, max_limit=200):
    limit = parse_int_param(
        request.query_params,
        "limit",
        default=default_limit,
        minimum=1,
        maximum=max_limit,
    )
    offset = parse_int_param(
        request.query_params,
        "offset",
        default=0,
        minimum=0,
    )

    total = queryset.count()
    items = queryset[offset : offset + limit]
    next_offset = offset + limit if offset + limit < total else None
    previous_offset = max(offset - limit, 0) if offset > 0 else None

    return {
        "data": serializer_class(items, many=True).data,
        "pagination": {
            "count": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
            "previous_offset": previous_offset,
        },
    }
