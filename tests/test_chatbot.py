import contextlib
import io
import os
import unittest
from unittest import mock

# Settings is evaluated at import time, so provide a complete test environment
# before importing the bot.
os.environ["TWITCH_OAUTH_TOKEN"] = "oauth:test"
os.environ["TWITCH_BOT_USERNAME"] = "testbot"
os.environ["TWITCH_CHANNEL"] = "testchannel"
os.environ["TWITCH_IRC_HOST"] = "irc.chat.twitch.tv"
os.environ["TWITCH_IRC_PORT"] = "6667"
os.environ["TWITCH_USERNAME_COLOR"] = "blue"
os.environ["SELF_PROMOTION_MESSAGE"] = ""

for name in [
    "SPOTIFY_USERNAME",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_PLAYLIST_ID",
]:
    os.environ[name] = ""

os.environ["SPOTIFY_REDIRECT_URI"] = "http://localhost/"

import ChatBot  # noqa: E402  (import after environment setup)


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.received = [b":tmi.twitch.tv 366 testbot #testchannel :End of /NAMES list\r\n"]

    def connect(self, address):
        pass

    def send(self, data):
        self.sent.append(data)

    def recv(self, size):
        if self.received:
            return self.received.pop(0)

        return b""


class ChatBotCommandTests(unittest.TestCase):
    def setUp(self):
        socket_patcher = mock.patch("socket.socket", FakeSocket)
        sleep_patcher = mock.patch("time.sleep", lambda seconds: None)
        socket_patcher.start()
        sleep_patcher.start()
        self.addCleanup(socket_patcher.stop)
        self.addCleanup(sleep_patcher.stop)

        with contextlib.redirect_stdout(io.StringIO()):
            self.bot = ChatBot.ChatBot()

        self.messages = []
        self.bot.send_text_to_channel = lambda channel, text: self.messages.append((channel, text))
        self.bot.print_with_timestamp = lambda text: None
        self.bot.print_with_timestamp_and_channel = lambda channel, text: None

    def chat(self, text, display="Viewer", badges=""):
        username = display.lower()
        line = (
            "@badges={};color=;display-name={};mod=0;subscriber=0 "
            ":{}!{}@{}.tmi.twitch.tv PRIVMSG #testchannel :{}"
        ).format(badges, display, username, username, username, text)
        self.bot.parse_line(line)

    def last_message(self):
        self.assertTrue(self.messages, "expected the bot to send a message")
        return self.messages[-1][1]

    def test_command_list_mentions_spotify_and_not_sockpuppets(self):
        self.chat("!commands")
        message = self.last_message()

        self.assertIn("!song", message)
        self.assertIn("!searchadd", message)
        self.assertNotIn("sockpuppets", message)

    def test_song_reports_nothing_when_spotify_is_disabled(self):
        self.chat("!song")

        self.assertEqual(self.last_message(), "Nothing is currently playing.")

    def test_addsong_without_a_code_shows_usage(self):
        self.chat("!addsong")

        self.assertIn("Usage: !addsong", self.last_message())

    def test_addsong_with_code_reports_spotify_disabled(self):
        self.chat("!addsong abc123")

        self.assertIn("Playlist functionality is currently off.", self.last_message())

    def test_searchsong_reports_spotify_disabled(self):
        self.chat("!searchsong pizza")

        self.assertIn("Playlist functionality is currently off.", self.last_message())

    def test_searchadd_reports_spotify_disabled(self):
        self.chat("!searchadd pizza")

        self.assertIn("Playlist functionality is currently off.", self.last_message())

    def test_meme_commands(self):
        cases = [
            ("!unbench", "UNBENCH THE KENCH"),
            ("!clown", "OVERCLOWNFIDENCE"),
            ("!jebaited", "Jebaited"),
        ]

        for command, fragment in cases:
            with self.subTest(command=command):
                self.messages.clear()
                self.chat(command)
                self.assertIn(fragment, self.last_message())

    def test_removed_sockpuppets_command_does_nothing(self):
        self.chat("!sockpuppets")

        self.assertEqual(self.messages, [])

    def test_passive_unbench_responds_to_the_phrase(self):
        self.chat("unbench the kench")

        self.assertIn("OSFrog", self.last_message())

    def test_playlist_off_clears_spotify_state(self):
        self.bot.spotify = object()
        self.bot.current_track = object()
        self.bot.oauth = object()

        self.chat("!playlist off", display="testchannel")

        self.assertIsNone(self.bot.spotify)
        self.assertIsNone(self.bot.current_track)
        self.assertIsNone(self.bot.oauth)

    def test_shut_down_calls_power_down(self):
        calls = []
        self.bot.power_down = lambda username: calls.append(username)

        self.chat("@testbot shut down", display="testchannel")

        self.assertEqual(calls, ["testchannel"])

    def test_broadcaster_begone_leaves_the_channel(self):
        self.chat("@testbot begone", display="testchannel", badges="broadcaster/1")

        self.assertNotIn("testchannel", self.bot.channel_list)

    def test_parse_line_tags(self):
        tags = "@badges=broadcaster/1;color=#FF0000;display-name=Naomi;" "mod=1;subscriber=1"

        info = self.bot.parse_line_tags(tags)

        self.assertEqual(info["username"], "Naomi")
        self.assertEqual(info["color"], "#FF0000")
        self.assertTrue(info["broadcaster"])
        self.assertTrue(info["moderator"])
        self.assertTrue(info["subscriber"])

    def test_parse_current_track_string(self):
        playing = {
            "is_playing": True,
            "item": {
                "name": "Song",
                "artists": [{"name": "Artist"}],
                "external_urls": {"spotify": "https://open.spotify.com/track/1"},
            },
        }

        self.assertEqual(
            self.bot.parse_current_track_string(playing),
            '"Song" by Artist https://open.spotify.com/track/1',
        )
        self.assertIsNone(self.bot.parse_current_track_string({"is_playing": False}))


if __name__ == "__main__":
    unittest.main()
