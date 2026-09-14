"""Tests for the announcement scheduling logic.

Standard library only, no Discord connection required:

    python tests/test_announcement_scheduling.py
    python -m unittest tests.test_announcement_scheduling
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

# Insert (not append) so the repo's own utils/ package wins over any same-named
# module that happens to sit earlier on PYTHONPATH.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from utils import announcement_scheduler as sched

# Expected values are built in the scheduler's own zone so these assertions hold
# whether the host is on UTC, Eastern, or anything else.
TZ = sched.get_tz()


def at(year, month, day, hour=0, minute=0, second=0):
    """Build an expected timestamp in the scheduler's configured zone."""
    return datetime(year, month, day, hour, minute, second, tzinfo=TZ)


FIXED_NOW = at(2026, 9, 14, 12, 0)  # Monday, noon


class DefaultTimezoneTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.pop("ANNOUNCEMENT_TIMEZONE", None)
        sched.reset_cache()

    def tearDown(self):
        if self._old is not None:
            os.environ["ANNOUNCEMENT_TIMEZONE"] = self._old
        else:
            os.environ.pop("ANNOUNCEMENT_TIMEZONE", None)
        sched.reset_cache()

    def test_defaults_to_new_york(self):
        self.assertEqual(str(sched.get_tz()), "America/New_York")
        self.assertEqual(sched.tz_label(), "America/New_York")

    def test_default_timestamps_are_zone_aware(self):
        parsed = sched.parse_when("2026-09-14 19:30")
        self.assertIsNotNone(parsed.tzinfo)
        self.assertIsNotNone(sched.current_time().tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), -4 * 3600, "EDT in September")

    def test_env_overrides_default(self):
        os.environ["ANNOUNCEMENT_TIMEZONE"] = "America/Chicago"
        sched.reset_cache()
        self.assertEqual(str(sched.get_tz()), "America/Chicago")
        self.assertEqual(sched.tz_label(), "America/Chicago")

    def test_blank_env_falls_back_to_default(self):
        os.environ["ANNOUNCEMENT_TIMEZONE"] = "   "
        sched.reset_cache()
        self.assertEqual(str(sched.get_tz()), "America/New_York")

    def test_unknown_zone_degrades_instead_of_crashing(self):
        os.environ["ANNOUNCEMENT_TIMEZONE"] = "Mars/Phobos"
        sched.reset_cache()
        self.assertIsNone(sched.get_tz())
        self.assertEqual(sched.tz_label(), "server local time")
        # Still has to produce usable times rather than exploding.
        parsed = sched.parse_when("2026-09-14 19:30")
        self.assertIsNone(parsed.tzinfo)
        self.assertEqual(parsed.replace(tzinfo=None), datetime(2026, 9, 14, 19, 30))

    def test_dst_boundary_offsets(self):
        # New York is UTC-4 in July and UTC-5 in January.
        summer = sched.parse_when("2026-07-14 12:00")
        winter = sched.parse_when("2026-01-14 12:00")
        self.assertEqual(summer.utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(winter.utcoffset().total_seconds(), -5 * 3600)


class ParseRelativeTests(unittest.TestCase):
    def test_short_units(self):
        self.assertEqual(sched.parse_when("30m", FIXED_NOW), FIXED_NOW + timedelta(minutes=30))
        self.assertEqual(sched.parse_when("2h", FIXED_NOW), FIXED_NOW + timedelta(hours=2))
        self.assertEqual(sched.parse_when("45s", FIXED_NOW), FIXED_NOW + timedelta(seconds=45))
        self.assertEqual(sched.parse_when("3d", FIXED_NOW), FIXED_NOW + timedelta(days=3))
        self.assertEqual(sched.parse_when("1w", FIXED_NOW), FIXED_NOW + timedelta(weeks=1))

    def test_compound_duration(self):
        self.assertEqual(sched.parse_when("1h30m", FIXED_NOW), FIXED_NOW + timedelta(hours=1, minutes=30))
        self.assertEqual(sched.parse_when("1h 30m", FIXED_NOW), FIXED_NOW + timedelta(hours=1, minutes=30))
        self.assertEqual(
            sched.parse_when("1 hour and 30 minutes", FIXED_NOW),
            FIXED_NOW + timedelta(hours=1, minutes=30),
        )
        self.assertEqual(
            sched.parse_when("1 day 2 hours", FIXED_NOW),
            FIXED_NOW + timedelta(days=1, hours=2),
        )

    def test_spelled_out_and_in_prefix(self):
        self.assertEqual(sched.parse_when("in 45 minutes", FIXED_NOW), FIXED_NOW + timedelta(minutes=45))
        self.assertEqual(sched.parse_when("2 hours", FIXED_NOW), FIXED_NOW + timedelta(hours=2))
        self.assertEqual(sched.parse_when("3 days", FIXED_NOW), FIXED_NOW + timedelta(days=3))

    def test_zero_and_negative_rejected(self):
        with self.assertRaises(ValueError):
            sched.parse_when("0m", FIXED_NOW)


class ParseInstantTests(unittest.TestCase):
    def test_instant_words(self):
        for word in ("now", "asap", "ASAP", "immediate", "right now"):
            self.assertEqual(sched.parse_when(word, FIXED_NOW), FIXED_NOW)


class ParseAbsoluteTests(unittest.TestCase):
    def test_iso_like(self):
        self.assertEqual(sched.parse_when("2026-09-14 19:30", FIXED_NOW), at(2026, 9, 14, 19, 30))
        self.assertEqual(sched.parse_when("2026-09-14 19:30:15", FIXED_NOW), at(2026, 9, 14, 19, 30, 15))
        self.assertEqual(sched.parse_when("2026-09-14T19:30", FIXED_NOW), at(2026, 9, 14, 19, 30))

    def test_us_style(self):
        self.assertEqual(sched.parse_when("09/14/2026 19:30", FIXED_NOW), at(2026, 9, 14, 19, 30))
        self.assertEqual(sched.parse_when("9/14/2026 7:30 PM", FIXED_NOW), at(2026, 9, 14, 19, 30))

    def test_twelve_hour_with_iso_date(self):
        self.assertEqual(sched.parse_when("2026-09-14 7:30 PM", FIXED_NOW), at(2026, 9, 14, 19, 30))

    def test_date_only_lands_at_default_hour(self):
        self.assertEqual(
            sched.parse_when("2026-09-14", FIXED_NOW),
            at(2026, 9, 14, sched.DEFAULT_HOUR, 0),
        )


class ParseBareTimeTests(unittest.TestCase):
    def test_later_today(self):
        self.assertEqual(sched.parse_when("19:30", FIXED_NOW), at(2026, 9, 14, 19, 30))

    def test_already_passed_rolls_to_tomorrow(self):
        self.assertEqual(sched.parse_when("09:00", FIXED_NOW), at(2026, 9, 15, 9, 0))

    def test_twelve_hour_bare(self):
        self.assertEqual(sched.parse_when("7:30 PM", FIXED_NOW), at(2026, 9, 14, 19, 30))


class ParseRelativeDayTests(unittest.TestCase):
    def test_today(self):
        self.assertEqual(sched.parse_when("today 17:00", FIXED_NOW), at(2026, 9, 14, 17, 0))

    def test_tomorrow(self):
        self.assertEqual(sched.parse_when("tomorrow 8:00", FIXED_NOW), at(2026, 9, 15, 8, 0))
        self.assertEqual(sched.parse_when("tomorrow 8:00 AM", FIXED_NOW), at(2026, 9, 15, 8, 0))


class ParseFailureTests(unittest.TestCase):
    def test_empty_and_garbage(self):
        for bad in ("", "   ", None, "banana", "sometime tuesday", "!!!"):
            with self.assertRaises(ValueError, msg="should reject {!r}".format(bad)):
                sched.parse_when(bad, FIXED_NOW)

    def test_datetime_is_not_swallowed_as_relative(self):
        # 2026-09-14 contains digits but no unit, so it must not be read as a duration.
        result = sched.parse_when("2026-09-14 19:30", FIXED_NOW)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.hour, 19)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.now = FIXED_NOW
        self.entries = [
            {"id": "a", "status": "pending", "send_at": sched.to_iso(self.now - timedelta(minutes=5))},
            {"id": "b", "status": "pending", "send_at": sched.to_iso(self.now + timedelta(minutes=5))},
            {"id": "c", "status": "pending", "send_at": sched.to_iso(self.now - timedelta(hours=2))},
            {"id": "d", "status": "sent", "send_at": sched.to_iso(self.now - timedelta(hours=3))},
            {"id": "e", "status": "cancelled", "send_at": sched.to_iso(self.now - timedelta(hours=3))},
        ]

    def test_due_only_returns_pending_and_past(self):
        due = sched.due_announcements(self.entries, self.now)
        self.assertEqual([d["id"] for d in due], ["c", "a"])  # oldest first

    def test_pending_sorted_by_send_time(self):
        pending = sched.pending_announcements(self.entries)
        self.assertEqual([p["id"] for p in pending], ["c", "a", "b"])

    def test_is_due_guards_bad_data(self):
        self.assertFalse(sched.is_due({"status": "pending", "send_at": "not-a-date"}, self.now))
        self.assertFalse(sched.is_due({"status": "pending"}, self.now))
        self.assertFalse(sched.is_due({"status": "sent", "send_at": sched.to_iso(self.now)}, self.now))

    def test_survives_reload_round_trip(self):
        # send_at is persisted as a string; due checks must work after a reload.
        entry = {"id": "x", "status": "pending", "send_at": sched.to_iso(self.now - timedelta(seconds=1))}
        reloaded = dict(entry)
        self.assertTrue(sched.is_due(reloaded, self.now))


class FormattingTests(unittest.TestCase):
    def test_ordinal_suffix(self):
        self.assertEqual(sched.ordinal_suffix(1), "st")
        self.assertEqual(sched.ordinal_suffix(2), "nd")
        self.assertEqual(sched.ordinal_suffix(3), "rd")
        self.assertEqual(sched.ordinal_suffix(4), "th")
        self.assertEqual(sched.ordinal_suffix(11), "th")
        self.assertEqual(sched.ordinal_suffix(21), "st")
        self.assertEqual(sched.ordinal_suffix(22), "nd")

    def test_humanize(self):
        self.assertEqual(sched.humanize(FIXED_NOW + timedelta(minutes=5), FIXED_NOW), "in 5 minutes")
        self.assertEqual(sched.humanize(FIXED_NOW + timedelta(hours=1), FIXED_NOW), "in 1 hour")
        self.assertEqual(sched.humanize(FIXED_NOW + timedelta(hours=2, minutes=5), FIXED_NOW), "in 2 hours 5 minutes")
        self.assertEqual(sched.humanize(FIXED_NOW - timedelta(days=1), FIXED_NOW), "1 day ago")

    def test_format_local_is_readable(self):
        text = sched.format_local(datetime(2026, 9, 14, 19, 30))
        self.assertIn("Sep", text)
        self.assertIn("14th", text)
        self.assertIn("2026", text)
        self.assertIn("07:30 PM", text)


class StorageRoundTripTests(unittest.TestCase):
    """send_at is persisted as an ISO string and re-read on every restart."""

    def setUp(self):
        self._old = os.environ.get("ANNOUNCEMENT_TIMEZONE")
        sched.reset_cache()

    def tearDown(self):
        if self._old is not None:
            os.environ["ANNOUNCEMENT_TIMEZONE"] = self._old
        else:
            os.environ.pop("ANNOUNCEMENT_TIMEZONE", None)
        sched.reset_cache()

    def test_aware_round_trip_through_storage(self):
        parsed = sched.parse_when("in 10 minutes")
        restored = sched.from_iso(sched.to_iso(parsed))
        self.assertEqual(parsed, restored)

    def test_past_timestamp_is_due_after_reload(self):
        past = sched.current_time() - timedelta(minutes=1)
        self.assertTrue(sched.is_due({"status": "pending", "send_at": sched.to_iso(past)}))

    def test_future_timestamp_is_not_due_after_reload(self):
        future = sched.current_time() + timedelta(minutes=10)
        self.assertFalse(sched.is_due({"status": "pending", "send_at": sched.to_iso(future)}))

    def test_zone_survives_round_trip(self):
        parsed = sched.parse_when("in 10 minutes")
        restored = sched.from_iso(sched.to_iso(parsed))
        self.assertEqual(str(restored.tzinfo), str(parsed.tzinfo))


if __name__ == "__main__":
    unittest.main(verbosity=2)
