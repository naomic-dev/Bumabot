import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_ENV = {
    "TWITCH_OAUTH_TOKEN": "oauth:test",
    "TWITCH_BOT_USERNAME": "TestBot",
    "TWITCH_CHANNEL": "TestChannel",
}


def run_settings(code, extra_env=None):
    env = os.environ.copy()

    for key in list(env):
        if (
            key.startswith("TWITCH_")
            or key.startswith("SPOTIFY_")
            or key == "SELF_PROMOTION_MESSAGE"
        ):
            env.pop(key, None)

    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env.update(extra_env or {})

    with tempfile.TemporaryDirectory() as working_directory:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=working_directory,
            env=env,
            capture_output=True,
            text=True,
        )


class SettingsTests(unittest.TestCase):
    def test_missing_token_fails_with_a_clear_message(self):
        result = run_settings(
            "import Settings",
            {
                "TWITCH_BOT_USERNAME": "bot",
                "TWITCH_CHANNEL": "channel",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TWITCH_OAUTH_TOKEN", result.stderr)
        self.assertIn("Copy .env.example", result.stderr)

    def test_normalizes_token_and_names(self):
        result = run_settings(
            "import Settings; "
            "print(Settings.PASS); "
            "print(Settings.NICK); "
            "print(Settings.CHANNEL); "
            "print(Settings.SPOTIFY_ENABLED)",
            BASE_ENV,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip().splitlines(),
            ["oauth:test", "testbot", "testchannel", "False"],
        )

    def test_default_irc_settings(self):
        result = run_settings(
            "import Settings; print(Settings.HOST); print(Settings.PORT); print(Settings.USE_TLS)",
            BASE_ENV,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip().splitlines(),
            ["irc.chat.twitch.tv", "6697", "True"],
        )

    def test_tls_can_be_disabled(self):
        env = dict(BASE_ENV)
        env["TWITCH_IRC_TLS"] = "false"

        result = run_settings("import Settings; print(Settings.USE_TLS)", env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_spotify_is_enabled_only_when_all_values_are_present(self):
        env = dict(BASE_ENV)
        env.update(
            {
                "SPOTIFY_USERNAME": "listener",
                "SPOTIFY_CLIENT_ID": "client-id",
                "SPOTIFY_CLIENT_SECRET": "client-secret",
                "SPOTIFY_PLAYLIST_ID": "playlist-id",
            }
        )

        result = run_settings("import Settings; print(Settings.SPOTIFY_ENABLED)", env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
