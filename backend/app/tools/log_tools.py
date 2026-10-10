"""
Log reading/search tool.

Reads and filters application log files. Like repo_tools, this is plain
deterministic Python — there's no reason to ask an LLM to do string
matching or filtering.

Expected log line format (see sample_project/logs/app.log):

    2026-09-10 08:12:03 | ERROR | request_id=a1b2c3d4 | POST /api/auth/login | KeyError: 'JWT_SECRET_KEY'
    <timestamp>          <level> <request_id>          <message...>

Lines that don't match this format are still returned (as a LogEntry with
level="UNKNOWN") rather than dropped — a real log tool shouldn't silently
throw away lines it doesn't understand.
"""

from pathlib import Path

from app.tools.models import LogEntry
from app.tools.security import resolve_within_root

_FIELD_SEPARATOR = " | "


def _parse_line(raw_line: str) -> LogEntry:
    parts = raw_line.split(_FIELD_SEPARATOR)

    if len(parts) < 3:
        # Doesn't match the expected format — keep it, but mark it unknown
        # rather than crashing or silently dropping a line that might
        # still matter to an investigation.
        return LogEntry(timestamp="", level="UNKNOWN", message=raw_line.strip(), raw_line=raw_line)

    timestamp, level = parts[0].strip(), parts[1].strip()
    request_id = None
    message_parts = parts[2:]

    if message_parts[0].startswith("request_id="):
        request_id = message_parts[0].removeprefix("request_id=").strip()
        message_parts = message_parts[1:]

    return LogEntry(
        timestamp=timestamp,
        level=level,
        request_id=request_id,
        message=_FIELD_SEPARATOR.join(message_parts).strip(),
        raw_line=raw_line,
    )


def read_log_entries(root: Path, log_relative_path: str) -> list[LogEntry]:
    """Read and parse every line of a log file into LogEntry objects."""
    log_path = resolve_within_root(root, log_relative_path)
    if not log_path.is_file():
        raise FileNotFoundError(f"No such log file: {log_relative_path}")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [_parse_line(line) for line in lines if line.strip()]


def search_logs(entries: list[LogEntry], keyword: str) -> list[LogEntry]:
    """Return entries whose message or raw line contains `keyword` (case-insensitive)."""
    keyword_lower = keyword.lower()
    return [
        entry
        for entry in entries
        if keyword_lower in entry.message.lower() or keyword_lower in entry.raw_line.lower()
    ]


def filter_by_level(entries: list[LogEntry], level: str) -> list[LogEntry]:
    """Return entries at exactly the given level, e.g. 'ERROR'."""
    level_upper = level.upper()
    return [entry for entry in entries if entry.level.upper() == level_upper]


def get_logs_by_request_id(entries: list[LogEntry], request_id: str) -> list[LogEntry]:
    """Return every entry tagged with the given request_id, in file order."""
    return [entry for entry in entries if entry.request_id == request_id]
