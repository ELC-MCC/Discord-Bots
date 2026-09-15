"""Tests for bot startup.

Covers which bots are allowed to run and what happens when one of them fails,
because a bot that silently does not start looks identical to a bot that is
running but broken.

    python tests/test_main_startup.py
"""

import asyncio
import contextlib
import io
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import discord

import bot_config
import main

TOKEN_ENV = {
    "Welcome Bot": "WELCOME_BOT_TOKEN",
    "Role Bot": "ROLE_MANAGER_TOKEN",
    "Event Bot": "EVENT_BOT_TOKEN",
    "Stream Bot": "STREAM_BOT_TOKEN",
    "Schedule Bot": "SCHEDULE_BOT_TOKEN",
    "Filament Bot": "FILAMENT_BOT_TOKEN",
    "Announcement Bot": "ANNOUNCEMENT_BOT_TOKEN",
}

ENABLE_FLAGS = {
    "Welcome Bot": "ENABLE_WELCOME_BOT",
    "Role Bot": "ENABLE_ROLE_BOT",
    "Event Bot": "ENABLE_EVENT_BOT",
    "Stream Bot": "ENABLE_STREAM_BOT",
    "Schedule Bot": "ENABLE_SCHEDULE_BOT",
    "Filament Bot": "ENABLE_FILAMENT_BOT",
    "Announcement Bot": "ENABLE_ANNOUNCEMENT_BOT",
}


def labels(specs):
    return [label for label, _, _ in specs]


def capture(func, *args, **kwargs):
    """Run func, returning (result, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


class PlanBotsTests(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in TOKEN_ENV.values()}
        self._flags = {k: getattr(bot_config, k) for k in ENABLE_FLAGS.values()}
        for flag in ENABLE_FLAGS.values():
            setattr(bot_config, flag, True)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in self._flags.items():
            setattr(bot_config, k, v)

    def set_tokens(self, **overrides):
        for label, env_var in TOKEN_ENV.items():
            os.environ[env_var] = overrides.get(label, "token-for-" + env_var)

    def test_all_tokens_present_starts_every_bot(self):
        self.set_tokens()
        specs, _ = capture(main.plan_bots, discord.Intents.none())
        self.assertEqual(sorted(labels(specs)), sorted(TOKEN_ENV.keys()))

    def test_blank_welcome_token_skips_only_the_welcome_bot(self):
        self.set_tokens(**{"Welcome Bot": ""})
        specs, _ = capture(main.plan_bots, discord.Intents.none())
        self.assertNotIn("Welcome Bot", labels(specs))
        self.assertEqual(len(specs), len(TOKEN_ENV) - 1, "the other bots must still start")

    def test_whitespace_token_is_treated_as_missing(self):
        self.set_tokens(**{"Welcome Bot": "   "})
        specs, _ = capture(main.plan_bots, discord.Intents.none())
        self.assertNotIn("Welcome Bot", labels(specs))

    def test_skip_is_announced_not_silent(self):
        self.set_tokens(**{"Welcome Bot": ""})
        _, output = capture(main.plan_bots, discord.Intents.none())
        self.assertIn("SKIPPED", output)
        self.assertIn("WELCOME_BOT_TOKEN", output, "the message must name the env var to fix")

    def test_disabled_flag_skips_bot(self):
        self.set_tokens()
        bot_config.ENABLE_WELCOME_BOT = False
        specs, output = capture(main.plan_bots, discord.Intents.none())
        self.assertNotIn("Welcome Bot", labels(specs))
        self.assertIn("disabled in bot_config.py", output)

    def test_no_tokens_returns_nothing(self):
        self.set_tokens(**{label: "" for label in TOKEN_ENV})
        specs, output = capture(main.plan_bots, discord.Intents.none())
        self.assertEqual(specs, [])
        self.assertEqual(output.count("SKIPPED"), len(TOKEN_ENV))

    def test_specs_carry_a_usable_builder(self):
        self.set_tokens()
        specs, _ = capture(main.plan_bots, discord.Intents.none())
        for label, token, build in specs:
            self.assertTrue(token)
            self.assertTrue(callable(build), f"{label} is missing a builder")


class FakeClient:
    def __init__(self, exc=None):
        self.exc = exc

    async def start(self, token):
        if self.exc is not None:
            raise self.exc
        return None


class _FakeResponse:
    status = 401
    reason = "Unauthorized"


class SuperviseTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_token_is_contained(self):
        _, output = await _run_supervise("Welcome Bot", discord.LoginFailure("bad token"))
        self.assertIn("LOGIN FAILED", output)
        self.assertIn("Welcome Bot", output)

    async def test_missing_privileged_intents_is_contained(self):
        _, output = await _run_supervise(
            "Welcome Bot", discord.PrivilegedIntentsRequired(None)
        )
        self.assertIn("PRIVILEGED INTENTS MISSING", output)
        self.assertIn("Server Members", output, "must name the intent to enable")

    async def test_generic_crash_is_contained(self):
        _, output = await _run_supervise("Welcome Bot", RuntimeError("kaboom"))
        self.assertIn("RuntimeError", output)
        self.assertIn("kaboom", output)

    async def test_constructor_failure_is_contained(self):
        def explode():
            raise ValueError("cannot build")

        _, output = await _run_supervise("Welcome Bot", None, build=explode)
        self.assertIn("could not be created", output)

    async def test_one_bad_bot_does_not_stop_the_others(self):
        # The point of supervision: a broken bot must not take the process down.
        started = []

        class GoodClient:
            async def start(self, token):
                started.append(token)

        results = await asyncio.gather(
            main.supervise_bot("Bad Bot", "x", lambda: FakeClient(discord.LoginFailure("nope"))),
            main.supervise_bot("Good Bot", "good-token", GoodClient),
            return_exceptions=True,
        )
        for result in results:
            self.assertIsNone(result, "supervise_bot must not raise")
        self.assertEqual(started, ["good-token"], "the healthy bot should still have run")

    async def test_supervise_returns_normally_when_bot_stops(self):
        results = await asyncio.gather(
            main.supervise_bot("Quiet Bot", "t", lambda: FakeClient()),
            return_exceptions=True,
        )
        self.assertIsNone(results[0])


async def _run_supervise(label, exc, build=None):
    if build is None:
        build = lambda: FakeClient(exc)  # noqa: E731
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        await main.supervise_bot(label, "token", build)
    return None, buf.getvalue()


if __name__ == "__main__":
    unittest.main(verbosity=2)
