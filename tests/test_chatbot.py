import contextlib
import datetime
import io
import os
import tempfile
import unittest
from unittest import mock

import Adventure

# Settings is evaluated at import time, so provide a complete test environment
# before importing the bot.
os.environ["TWITCH_OAUTH_TOKEN"] = "oauth:test"
os.environ["TWITCH_BOT_USERNAME"] = "testbot"
os.environ["TWITCH_CHANNEL"] = "testchannel"
os.environ["TWITCH_IRC_HOST"] = "irc.chat.twitch.tv"
os.environ["TWITCH_IRC_PORT"] = "6697"
os.environ["TWITCH_IRC_TLS"] = "false"
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

    def settimeout(self, timeout):
        pass

    def close(self):
        pass


class ChatBotCommandTests(unittest.TestCase):
    def setUp(self):
        socket_patcher = mock.patch(
            "socket.create_connection", lambda *args, **kwargs: FakeSocket()
        )
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

    def test_add_track_uses_playlist_add_items(self):
        class FakeSpotify:
            def __init__(self):
                self.calls = []

            def playlist_add_items(self, playlist_id, items):
                self.calls.append((playlist_id, items))
                return {}

        fake = FakeSpotify()
        self.bot.spotify = fake

        with mock.patch.object(ChatBot, "SPOTIFY_PLAYLIST_ID", "playlist-1"):
            self.bot.add_track_to_playlist("track-1", "Viewer")

        self.assertEqual(fake.calls, [("playlist-1", ["track-1"])])
        self.assertIn("Added song to playlist.", self.last_message())

    def test_search_uses_the_q_parameter(self):
        class FakeSpotify:
            def __init__(self):
                self.kwargs = None

            def search(self, **kwargs):
                self.kwargs = kwargs
                return {"tracks": {"items": []}}

        fake = FakeSpotify()
        self.bot.spotify = fake

        self.bot.search_for_spotify_song("pizza", "Viewer")

        self.assertEqual(fake.kwargs, {"q": "pizza", "type": "track", "limit": 5})
        self.assertIn("No results found.", self.last_message())

    def test_update_spotify_token_recreates_the_client(self):
        class FakeCache:
            def get_cached_token(self):
                return {"refresh_token": "refresh"}

        class FakeOAuth:
            def __init__(self):
                self.cache_handler = FakeCache()

            def validate_token(self, token_info):
                return {"access_token": "new-token"}

        class FakeSpotify:
            def __init__(self, auth=None):
                self.auth = auth

        self.bot.oauth = FakeOAuth()
        self.bot.spotipy_token = "old-token"

        with mock.patch.object(ChatBot.spotipy, "Spotify", FakeSpotify):
            self.bot.update_spotify_token()

        self.assertEqual(self.bot.spotipy_token, "new-token")
        self.assertIsInstance(self.bot.spotify, FakeSpotify)
        self.assertEqual(self.bot.spotify.auth, "new-token")

    def test_init_spotify_uses_a_cached_token(self):
        class FakeOAuth:
            def __init__(self, **kwargs):
                self.cache_handler = self

            def get_cached_token(self):
                return {"access_token": "cached-token"}

            def validate_token(self, token_info):
                return token_info

        class FakeSpotify:
            def __init__(self, auth=None):
                self.auth = auth

            def current_user_playing_track(self):
                return None

        with mock.patch.object(ChatBot, "SPOTIFY_ENABLED", True), mock.patch.object(
            ChatBot.spotipy.oauth2, "SpotifyOAuth", FakeOAuth
        ), mock.patch.object(ChatBot.spotipy, "Spotify", FakeSpotify), mock.patch.object(
            self.bot, "update_now_playing_file"
        ):
            self.bot.init_spotify()

        self.assertEqual(self.bot.spotipy_token, "cached-token")
        self.assertIsInstance(self.bot.spotify, FakeSpotify)
        self.assertEqual(self.bot.spotify.auth, "cached-token")

    def test_update_current_track_writes_the_overlay(self):
        playing = {
            "is_playing": True,
            "item": {
                "name": "Song",
                "artists": [{"name": "Artist"}],
                "external_urls": {"spotify": "https://open.spotify.com/track/1"},
            },
        }

        class FakeSpotify:
            def current_user_playing_track(self):
                return playing

        self.bot.spotify = FakeSpotify()
        self.bot.current_track = None

        with tempfile.TemporaryDirectory() as directory:
            current_directory = os.getcwd()
            os.chdir(directory)

            try:
                self.bot.update_current_track()

                with open("spotify_now_playing.txt", encoding="utf-8") as file:
                    overlay = file.read()
            finally:
                os.chdir(current_directory)

        self.assertEqual(overlay, "Listening to Song - Artist")
        self.assertEqual(
            self.bot.current_track,
            '"Song" by Artist https://open.spotify.com/track/1',
        )

    def test_open_socket_uses_plain_socket_when_tls_is_disabled(self):
        with mock.patch.object(ChatBot, "USE_TLS", False):
            result = self.bot.open_socket()

        self.assertIsInstance(result, FakeSocket)

    def test_open_socket_wraps_tls_and_verifies_the_host(self):
        class FakeContext:
            def __init__(self):
                self.raw_socket = None
                self.server_hostname = None
                self.wrapped_socket = mock.Mock()

            def wrap_socket(self, raw_socket, server_hostname):
                self.raw_socket = raw_socket
                self.server_hostname = server_hostname
                return self.wrapped_socket

        context = FakeContext()

        with mock.patch.object(ChatBot, "USE_TLS", True), mock.patch.object(
            ChatBot.ssl, "create_default_context", return_value=context
        ) as create_context, mock.patch.object(
            ChatBot.certifi, "where", return_value="/tmp/ca.pem"
        ):
            result = self.bot.open_socket()

        create_context.assert_called_once_with(cafile="/tmp/ca.pem")
        self.assertIsInstance(context.raw_socket, FakeSocket)
        self.assertEqual(context.server_hostname, "irc.chat.twitch.tv")
        self.assertIs(result, context.wrapped_socket)

    def test_start_adventure_creates_a_town_adventure(self):
        self.bot.start_adventure("testchannel")

        adventure = self.bot.adventure_list["testchannel"]

        self.assertEqual(adventure.location, Adventure.Locations.town)
        self.assertTrue(any("Adventure started!" in text for _, text in self.messages))
        self.assertTrue(any("peaceful mountain town" in text for _, text in self.messages))

    def test_start_adventure_twice_warns(self):
        self.bot.start_adventure("testchannel")
        self.messages.clear()

        self.bot.start_adventure("testchannel")

        self.assertIn("already running", self.last_message())

    def test_enter_dungeon_changes_location(self):
        self.bot.start_adventure("testchannel")
        self.messages.clear()

        self.bot.enter_dungeon("testchannel")

        adventure = self.bot.adventure_list["testchannel"]
        self.assertEqual(adventure.location, Adventure.Locations.dungeon)
        self.assertIn("dungeon", self.last_message())

    def test_stop_adventure_removes_it(self):
        self.bot.start_adventure("testchannel")

        self.bot.stop_adventure("testchannel")

        self.assertNotIn("testchannel", self.bot.adventure_list)
        self.assertIn("Adventure stopped.", self.last_message())

    def test_owner_can_start_an_adventure(self):
        self.chat("!adventure start", display="testchannel")

        self.assertIn("testchannel", self.bot.adventure_list)

    def test_players_can_join_and_attack(self):
        self.bot.start_adventure("testchannel")
        self.bot.enter_dungeon("testchannel")
        self.messages.clear()

        self.chat("!join")
        adventure = self.bot.adventure_list["testchannel"]

        self.assertIn("Viewer", adventure.player_list)
        self.assertTrue(any("has joined the party" in text for _, text in self.messages))

        self.messages.clear()
        self.chat("!attack")

        self.assertNotEqual(self.messages, [])
        self.assertIn("Viewer", adventure.player_list)

    def test_update_adventures_auto_enters_the_dungeon(self):
        self.bot.start_adventure("testchannel")
        adventure = self.bot.adventure_list["testchannel"]
        adventure.location_time = datetime.datetime.now() - datetime.timedelta(minutes=6)
        self.messages.clear()

        self.bot.update_adventures()

        self.assertEqual(adventure.location, Adventure.Locations.dungeon)
        self.assertTrue(any("dungeon" in text for _, text in self.messages))

    def test_update_adventures_runs_boss_attacks(self):
        self.bot.start_adventure("testchannel")
        self.bot.enter_dungeon("testchannel")
        adventure = self.bot.adventure_list["testchannel"]
        adventure.add_player("Viewer")
        boss = adventure.boss_list[adventure.level_counter]
        boss.last_attack_time = None
        self.messages.clear()

        self.bot.update_adventures()

        self.assertTrue(self.messages)
        self.assertIsNotNone(boss.last_attack_time)


if __name__ == "__main__":
    unittest.main()
