"""
Announcement scheduling helpers.

Pure standard library on purpose: the time parsing and "is it due yet" logic is
the part that breaks in production, so it lives here where it can be tested
without a Discord connection (see tests/test_announcement_scheduling.py).

Time handling: every timestamp this module produces is anchored to DEFAULT_TIMEZONE
(New York unless ANNOUNCEMENT_TIMEZONE overrides it). Anchoring to a named zone means
typed times mean what the club means by them even when the host clock is set to UTC,
which is the usual state of a fresh server. datetime.now(tz) is derived from the
machine's UTC clock, so the wall time is correct regardless of the host's own setting.

If the zone cannot be loaded the module degrades to naive host-local time and warns
once, rather than taking the whole bot process down with it.
"""

import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


# --- Timezone plumbing -------------------------------------------------------

DEFAULT_TIMEZONE = "America/New_York"

_warned_about_zone = False


@lru_cache(maxsize=1)
def get_tz():
    """Zone every timestamp is anchored to, or None if it could not be loaded."""
    global _warned_about_zone

    if ZoneInfo is None:  # pragma: no cover - only on bare Python installs
        _warn_once("zoneinfo is unavailable; using host local time")
        return None

    name = (os.getenv("ANNOUNCEMENT_TIMEZONE") or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception as exc:
        _warn_once("unknown timezone {!r} ({}); using host local time".format(name, exc))
        return None


def _warn_once(message: str) -> None:
    global _warned_about_zone
    if not _warned_about_zone:
        print("AnnouncementScheduler: {}".format(message))
        _warned_about_zone = True


def reset_cache() -> None:
    """Drop cached timezone state. Used by tests after patching the env var."""
    global _warned_about_zone
    _warned_about_zone = False
    get_tz.cache_clear()


def tz_label() -> str:
    tz = get_tz()
    if tz is None:
        return "server local time"
    return str(tz)


def current_time() -> datetime:
    """The clock this module schedules against."""
    tz = get_tz()
    if tz is None:
        return datetime.now()
    return datetime.now(tz)


def _attach(dt: datetime) -> datetime:
    """Stamp the configured timezone onto a naive datetime."""
    tz = get_tz()
    if tz is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


# --- Formatting -------------------------------------------------------------


def ordinal_suffix(day: int) -> str:
    if 4 <= day <= 20 or 24 <= day <= 30:
        return "th"
    return ["st", "nd", "rd"][day % 10 - 1]


def format_local(dt: datetime) -> str:
    """Human readable stamp, e.g. 'Mon Sep 14th, 2026 at 07:30 PM'."""
    return "{} {}{}, {} at {}".format(
        dt.strftime("%a %b"),
        dt.day,
        ordinal_suffix(dt.day),
        dt.year,
        dt.strftime("%I:%M %p"),
    )


def format_with_zone(dt: datetime) -> str:
    return "{} ({})".format(format_local(dt), tz_label())


def humanize(dt: datetime, ref: Optional[datetime] = None) -> str:
    """'in 2 hours 5 minutes' / '4 minutes ago'."""
    ref = ref if ref is not None else current_time()
    seconds = (dt - ref).total_seconds()
    past = seconds < 0
    seconds = abs(seconds)

    if seconds < 45:
        return "just now" if not past else "moments ago"

    chunks = []
    for label, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            count = int(seconds // size)
            seconds -= count * size
            chunks.append("{} {}{}".format(count, label, "" if count == 1 else "s"))
        if len(chunks) == 2:
            break

    if not chunks:  # pragma: no cover - covered by the <45 branch
        return "less than a minute ago" if past else "in less than a minute"

    text = " ".join(chunks)
    return "{} ago".format(text) if past else "in {}".format(text)


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def from_iso(text: str) -> datetime:
    """Read a stored timestamp back, re-anchored to the configured zone.

    datetime.isoformat() records the offset but not the zone name, so without
    this a restored value would carry a bare fixed offset. Re-anchoring keeps
    every datetime in the system expressed in one zone, and re-expressing an
    instant never changes which moment it refers to.
    """
    dt = datetime.fromisoformat(text)
    tz = get_tz()
    if tz is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


# --- Parsing -----------------------------------------------------------------

# Longest alternatives first so 'mins' wins over 'm' and 'hours' over 'h'.
_UNIT_SECONDS: Dict[str, int] = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "wk": 604800, "wks": 604800, "week": 604800, "weeks": 604800,
}

_REL_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|wks?|w)"
    r"(?![a-z])",
    re.IGNORECASE,
)

_INSTANT_WORDS = {"now", "asap", "immediate", "immediately", "right now", "instantly"}

_ABSOLUTE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %I:%M %p",
    "%Y-%m-%d %I:%M%p",
    "%Y/%m/%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %I:%M%p",
    "%m/%d/%y %H:%M",
    "%m/%d/%y %I:%M %p",
    "%B %d, %Y %H:%M",
    "%B %d %Y %H:%M",
    "%b %d, %Y %H:%M",
    "%b %d %Y %H:%M",
)

_DATE_ONLY_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
)

_TIME_ONLY_FORMATS = (
    "%H:%M:%S",
    "%H:%M",
    "%I:%M %p",
    "%I:%M%p",
    "%I %p",
)

# A date typed without a time lands at 9am, a bare time with no date lands on the
# next occurrence of that time.
DEFAULT_HOUR = 9

HELP_TEXT = (
    "Tell me when to send, for example:\n"
    "`30m` / `2h` / `1h30m` / `3 days` - counted from right now\n"
    "`in 45 minutes` - same thing, spelled out\n"
    "`2026-09-14 19:30` or `09/14/2026 7:30 PM` - an exact date and time\n"
    "`19:30` - today at 7:30 PM, or tomorrow if that already passed\n"
    "`tomorrow 8:00` - tomorrow morning\n"
    "`2026-09-14` - that date at 9:00 AM\n"
    "`now` - send on the next check (within about 20 seconds)"
)


def _parse_time_of_day(text: str) -> Optional[object]:
    text = text.strip().replace(".", "").upper()
    text = re.sub(r"\s+", " ", text)
    for fmt in _TIME_ONLY_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_when(text: str, now: Optional[datetime] = None) -> datetime:
    """Turn human input into the datetime an announcement should fire.

    Raises ValueError with a friendly message when the input cannot be read.
    """
    if text is None or not str(text).strip():
        raise ValueError("No send time given.\n\n" + HELP_TEXT)

    raw = str(text).strip()
    low = raw.lower()
    ref = now if now is not None else current_time()

    if low in _INSTANT_WORDS:
        return ref

    # --- Relative: 30m, 2h, 1h30m, in 3 days, 1 hour and 30 minutes ----------
    body = re.sub(r"^in\s+", "", low)
    matches = _REL_RE.findall(body)
    if matches:
        leftover = _REL_RE.sub(" ", body)
        leftover = re.sub(r"\b(and)\b", " ", leftover).replace(",", " ")
        leftover = leftover.replace("+", " ")
        if leftover.strip() == "":
            total = 0.0
            for number, unit in matches:
                total += float(number) * _UNIT_SECONDS[unit.lower()]
            if total <= 0:
                raise ValueError("That time is not in the future.\n\n" + HELP_TEXT)
            return ref + timedelta(seconds=total)

    # --- today / tomorrow + time -------------------------------------------
    m = re.match(r"^(today|tomorrow|tonight)\s+(.+)$", low)
    if m:
        word, rest = m.group(1), m.group(2)
        parsed = _parse_time_of_day(rest)
        if parsed is None:
            raise ValueError("Could not read the time in '{}'.\n\n{}".format(raw, HELP_TEXT))
        day = ref.date()
        if word == "tomorrow":
            day = day + timedelta(days=1)
        return _attach(datetime.combine(day, parsed))

    # --- Absolute date + time ----------------------------------------------
    for fmt in _ABSOLUTE_FORMATS:
        try:
            return _attach(datetime.strptime(raw, fmt))
        except ValueError:
            continue

    # --- Date only ----------------------------------------------------------
    for fmt in _DATE_ONLY_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return _attach(parsed.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0))

    # --- Bare time ----------------------------------------------------------
    parsed_time = _parse_time_of_day(raw)
    if parsed_time is not None:
        candidate = _attach(datetime.combine(ref.date(), parsed_time))
        if candidate <= ref:
            candidate = candidate + timedelta(days=1)
        return candidate

    raise ValueError("Could not understand '{}'.\n\n{}".format(raw, HELP_TEXT))


# --- Queue helpers -----------------------------------------------------------


def is_due(entry: Dict, now: Optional[datetime] = None) -> bool:
    if entry.get("status") != "pending":
        return False
    when = entry.get("send_at")
    if not when:
        return False
    try:
        return from_iso(when) <= (now if now is not None else current_time())
    except (ValueError, TypeError):
        return False


def due_announcements(announcements: List[Dict], now: Optional[datetime] = None) -> List[Dict]:
    """Pending entries whose send time has arrived, oldest first."""
    return sorted(
        [a for a in announcements if is_due(a, now)],
        key=lambda a: a.get("send_at") or "",
    )


def pending_announcements(announcements: List[Dict]) -> List[Dict]:
    return sorted(
        [a for a in announcements if a.get("status") == "pending"],
        key=lambda a: a.get("send_at") or "",
    )
