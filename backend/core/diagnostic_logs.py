import re
from pathlib import Path

from django.conf import settings


LOG_HEADER_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+:\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+-\s+(?P<message>.*)$"
)
TRACE_FRAME_RE = re.compile(
    r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<function>.+)$'
)
EXCEPTION_TYPE_RE = re.compile(
    r"^(?P<type>(?:[A-Za-z_]\w*\.)*"
    r"(?:[A-Za-z_]\w*(?:Error|Exception|Interrupt)|Timeout))(?::|$)"
)
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
MAC_RE = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
)
IPV4_RE = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?:/\d{1,2})?(?![\d.])"
)
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
CREDENTIAL_RE = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key|authorization)\b"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)
PRIVATE_PATH_RE = re.compile(
    r"(?<!\w)(?:/Users/[^\s'\"]+|/home/[^\s'\"]+|/app/[^\s'\"]+|/data/[^\s'\"]+)"
)


def sanitize_log_message(value, redacted_values=()):
    message = str(value or "").strip()
    message = URL_RE.sub("[url]", message)
    message = MAC_RE.sub("[mac]", message)
    message = IPV4_RE.sub("[ip]", message)
    message = EMAIL_RE.sub("[email]", message)
    message = CREDENTIAL_RE.sub(lambda match: f"{match.group(1)}=[redacted]", message)
    message = PRIVATE_PATH_RE.sub("[path]", message)
    for private_value in redacted_values:
        pattern = re.escape(private_value)
        if private_value[0].isalnum():
            pattern = rf"(?<!\w){pattern}"
        if private_value[-1].isalnum():
            pattern = rf"{pattern}(?!\w)"
        message = re.sub(pattern, "[private]", message, flags=re.IGNORECASE)
    return message[:500]


def _safe_frame_path(value):
    parts = [part for part in str(value or "").replace("\\", "/").split("/") if part]
    if not parts:
        return "unknown"
    for marker in ("core", "backend"):
        if marker in parts:
            return "/".join(parts[parts.index(marker) :])[-240:]
    return "/".join(parts[-3:])[-240:]


def parse_diagnostic_log(text, component, redacted_values=()):
    events = []
    current = None

    def finish_current():
        if not current or current["level"] not in {"WARNING", "ERROR", "CRITICAL"}:
            return
        frames = []
        exception_type = ""
        for line in current.pop("context"):
            frame_match = TRACE_FRAME_RE.match(line)
            if frame_match and len(frames) < 12:
                frames.append(
                    {
                        "file": _safe_frame_path(frame_match.group("path")),
                        "line": int(frame_match.group("line")),
                            "function": sanitize_log_message(
                                frame_match.group("function"), redacted_values
                            ),
                    }
                )
                continue
            exception_match = EXCEPTION_TYPE_RE.match(line.strip())
            if exception_match:
                exception_type = exception_match.group("type")[-120:]
        current["traceback"] = frames
        current["exception_type"] = exception_type
        events.append(current.copy())

    for raw_line in str(text or "").splitlines():
        header_match = LOG_HEADER_RE.match(raw_line)
        if header_match:
            finish_current()
            current = {
                "timestamp": header_match.group("timestamp"),
                "component": component,
                "level": header_match.group("level"),
                "message": sanitize_log_message(
                    header_match.group("message"), redacted_values
                ),
                "context": [],
            }
        elif current is not None:
            current["context"].append(raw_line)
    finish_current()
    return events


def _component_log_paths():
    configured = getattr(settings, "DIAGNOSTIC_LOG_FILES", {})
    if isinstance(configured, dict):
        return {str(key): Path(value) for key, value in configured.items()}
    return {"backend": Path(settings.LOG_FILE)}


def _read_component_log(path, backup_count):
    chunks = []
    candidates = [Path(f"{path}.{index}") for index in range(backup_count, 0, -1)]
    candidates.append(path)
    available = False
    for candidate in candidates:
        try:
            chunks.append(candidate.read_text(encoding="utf-8", errors="replace"))
            available = True
        except OSError:
            continue
    return "\n".join(chunks), available


def collect_diagnostic_logs(max_events=120, redacted_values=()):
    events = []
    sources = []
    redacted_values = tuple(
        sorted(
            {
                str(value).strip()
                for value in redacted_values
                if len(str(value).strip()) >= 3
                and str(value).strip().lower() not in {"device", "unknown"}
            },
            key=len,
            reverse=True,
        )
    )
    backup_count = max(0, int(getattr(settings, "LOG_BACKUP_COUNT", 3)))
    for component, path in _component_log_paths().items():
        text, available = _read_component_log(path, backup_count)
        component_events = parse_diagnostic_log(text, component, redacted_values)
        events.extend(component_events)
        sources.append(
            {
                "component": component,
                "available": available,
                "warning_error_events_found": len(component_events),
            }
        )
    events.sort(key=lambda event: event["timestamp"])
    return {
        "included_levels": ["WARNING", "ERROR", "CRITICAL"],
        "events_limit": max_events,
        "sources": sources,
        "events": events[-max_events:],
    }
