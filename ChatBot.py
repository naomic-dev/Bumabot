"""Twitch IRC chat bot: socket loop, command routing, and Spotify integration."""

import datetime
import logging
import random
import select
import socket
import time
from typing import Any, Dict, Optional

# For Spotify integration
import spotipy
import spotipy.oauth2
import spotipy.util as util

# Import local files
from Settings import (
    HOST,
    PORT,
    PASS,
    NICK,
    CHANNEL,
    USERNAME_COLOR,
    SELF_PROMOTION_MESSAGE,
    SPOTIFY_ENABLED,
    SPOTIFY_USERNAME,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_PLAYLIST_ID,
)
import Adventure
import Memes

log = logging.getLogger(__name__)


class ChatBot:
    """A Twitch IRC chat bot."""

    def __init__(self) -> None:
        self.host = HOST
        self.port = PORT
        self.password = PASS
        self.username = NICK
        self.channel = CHANNEL
        self.username_color = USERNAME_COLOR

        self.socket = socket.socket()

        # Store joined channels here, remove them when leaving, check on each leave to see if we should stop reading
        self.channel_list = []

        self.adventure_list = {}

        # Connect to Twitch IRC
        self.socket.connect((self.host, self.port))

        # Tell the server we'd like to see users' membership levels
        self.send_encoded("CAP REQ :twitch.tv/membership")
        # Tell the server we'd like to see tags for users' messages
        self.send_encoded("CAP REQ :twitch.tv/tags")

        # Send password
        self.send_encoded("PASS {}".format(self.password))

        # Send username
        self.send_encoded("NICK {}".format(self.username))

        self.join_channel(self.channel)

        # Spotify stuff
        self.spotify = None
        self.current_track = None
        self.oauth = None

        self.init_spotify()
        self.token_expiry = datetime.datetime.now() + datetime.timedelta(hours=1)

        self.bot_info_sleep_timer = datetime.datetime.now() + datetime.timedelta(minutes=15)
        self.bot_info_message = "Type !commands to see what orders you can give me."

        self.self_promotion_sleep_timer = datetime.datetime.now() + datetime.timedelta(minutes=15)
        self.self_promotion_message = SELF_PROMOTION_MESSAGE

        self.idle_chat_sleep_timer = datetime.datetime.now() + datetime.timedelta(minutes=10)
        self.idle_messages = [
            "Anyone in here?",
            "ResidentSleeper",
            "Dead chat SeemsGood",
            "Every day is TransgenderPride Pride Day TransgenderPride in this house",
            "PogChamp MODS ARE ASLEEP!! POST YOUR DANK MEMES PogChamp",
        ]

    def join_channel(self, channel: str) -> None:
        """Join a channel and wait for the initial NAMES list."""
        self.send_encoded("JOIN #{}".format(channel))

        # Init read buffer. String containing information passed to/from socket
        read_buffer = ""

        # Init escape variable
        loading = True

        while loading:
            # Read information into the socket in 1024 bit (maybe byte) increments
            read_buffer = read_buffer + self.socket.recv(1024).decode()

            # Split the read_buffer into a stack, using linebreaks as a delimiter
            temp_buffer = read_buffer.split("\n")

            # Pop line off the top of the stack
            read_buffer = temp_buffer.pop()

            for line in temp_buffer:
                log.debug(line)

                # Test to see if initializing is finished
                loading = self.still_loading(channel, line)

        self.change_username_color(channel, self.username_color)
        self.channel_list.append(channel)

    def still_loading(self, channel: str, line: str) -> bool:
        if "#{} :End of /NAMES list".format(channel) in line:
            return False
        else:
            return True

    def leave_channel(self, channel: str) -> None:
        """Leave a channel and update the channel list."""
        self.send_encoded("PART #{}".format(channel))
        self.channel_list.remove(channel)

    def power_down(self, username: str) -> None:
        """Leave every channel and clear the now-playing file."""
        # Leave the all rooms and finish the loop
        self.print_with_timestamp("COMMAND: Power Down ({})".format(username))

        # Create a copy of the channel list so we have a list to work from that won't be edited as we remove channels
        channel_list = list(self.channel_list)

        for channel in channel_list:
            self.print_with_timestamp_and_channel(channel, "Parting")
            self.print_with_timestamp("Powering down.")
            self.leave_channel(channel)

        with open("spotify_now_playing.txt", "w+") as file:
            file.write("")

    def send_encoded(self, text: str) -> None:
        """Send one IRC line to the server."""
        text_with_new_line = text + "\r\n"
        self.socket.send(text_with_new_line.encode("utf-8"))

    def send_text_to_channel(self, channel: str, text: str) -> None:
        """Send a PRIVMSG to a channel."""
        self.send_encoded("PRIVMSG #{} :{}".format(channel, text))
        time.sleep(1.5)

    def send_text_to_default_chat(self, text: str) -> None:
        """Send a message to the bot's configured channel."""
        # Format the message for IRC and send it
        self.send_text_to_channel(self.channel, text)

    def get_users_in_channel(self, channel: str) -> None:
        """Request the channel's user list."""
        self.send_encoded("NAMES #{}".format(channel))

    def change_username_color(self, channel: str, color: str) -> None:
        """Set the bot's chat color."""
        self.send_text_to_channel(channel, "/color {}".format(color))

    # Log a timestamped message.
    def print_with_timestamp(self, text: str) -> None:
        log.info(text)

    # Log a timestamped message with the channel name.
    def print_with_timestamp_and_channel(self, channel: str, text: str) -> None:
        if channel:
            log.info("[%s] %s", channel, text)
        else:
            log.info(text)

    def get_channel_from_line(self, line: str) -> Optional[str]:
        """Extract a channel name from an IRC line."""
        if "#" not in line:
            return None

        split_line = line.split("#", 1)
        return split_line[1].split()[0]

    def parse_line_tags(self, tags: str) -> Dict[str, object]:
        """Parse IRC tags into a user-info dictionary."""
        color = ""
        username = ""
        broadcaster = False
        moderator = False
        subscriber = False

        if ";" in tags:
            split_tags = tags.split(";")

            for tag in split_tags:
                if "color=" in tag:
                    color = tag.split("=")[1]
                elif "display-name=" in tag:
                    username = tag.split("=")[1]
                elif "@badges=" in tag and "broadcaster/" in tag:
                    broadcaster = True
                elif tag == "mod=1":
                    moderator = True
                elif tag == "subscriber=1":
                    subscriber = True

        return {
            "username": username,
            "broadcaster": broadcaster,
            "moderator": moderator,
            "subscriber": subscriber,
            "color": color,
        }

    def init_spotify(self, refreshing_token: bool = False) -> None:
        """Initialize the Spotify client and current-track cache."""
        if not SPOTIFY_ENABLED:
            if not refreshing_token:
                self.print_with_timestamp("Spotify disabled (missing credentials).")

            return

        # Init Spotipy listening
        self.spotipy_scope = "user-read-currently-playing playlist-modify-public"

        self.spotipy_token = util.prompt_for_user_token(
            SPOTIFY_USERNAME,
            self.spotipy_scope,
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
        )

        self.oauth = spotipy.oauth2.SpotifyOAuth(
            SPOTIFY_CLIENT_ID,
            SPOTIFY_CLIENT_SECRET,
            SPOTIFY_REDIRECT_URI,
            scope=self.spotipy_scope,
            cache_path=".cache-{}".format(SPOTIFY_USERNAME),
        )

        self.spotify = spotipy.Spotify(auth=self.spotipy_token)
        self.current_track = self.parse_current_track_string(
            self.spotify.current_user_playing_track()
        )

        if self.current_track is not None:
            with open("spotify_now_playing.txt", "w+") as file:
                file.write(
                    "Listening to {}".format(
                        self.parse_current_track_string_for_overlay(
                            self.spotify.current_user_playing_track()
                        )
                    )
                )

        if not refreshing_token:
            self.print_with_timestamp("Spotify functionality enabled.")

    def update_spotify_token(self) -> None:
        """Refresh the cached Spotify token when needed."""
        if self.oauth is not None:
            token_info = self.oauth.get_cached_token()

            if token_info is not None and self.token_expiry <= datetime.datetime.now():
                new_token_info = self.oauth.refresh_access_token(token_info["refresh_token"])
                self.spotipy_token = new_token_info["access_token"]
                self.spotify._auth = self.spotipy_token

                self.token_expiry = datetime.datetime.now() + datetime.timedelta(hours=1)
                self.print_with_timestamp("Refreshed Spotify token.")
            elif token_info is None:
                self.print_with_timestamp("Token Info not found.")

    def parse_current_track_string(
        self, current_track_string: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Format the current track for chat."""
        if current_track_string is not None and current_track_string["is_playing"]:
            return '"{}" by {} {}'.format(
                current_track_string["item"]["name"],
                current_track_string["item"]["artists"][0]["name"],
                current_track_string["item"]["external_urls"]["spotify"],
            )
        else:
            return None

    def parse_current_track_string_for_overlay(
        self, current_track_string: Optional[Dict[str, Any]]
    ) -> str:
        """Format the current track for the overlay file."""
        if current_track_string is not None and current_track_string["is_playing"]:
            item = current_track_string["item"]

            return "{} - {}".format(item["name"], item["artists"][0]["name"])

        return ""

    def update_current_track(self) -> None:
        """Poll Spotify and update the now-playing overlay."""
        try:
            temp_current_track = self.parse_current_track_string(
                self.spotify.current_user_playing_track()
            )

            if self.current_track != temp_current_track:
                self.current_track = temp_current_track

                with open("spotify_now_playing.txt", "w+") as file:
                    if self.current_track is not None:
                        file.write(
                            "Listening to {}".format(
                                self.parse_current_track_string_for_overlay(
                                    self.spotify.current_user_playing_track()
                                )
                            )
                        )
                    else:
                        file.write("")
        except:
            token_info = self.oauth.get_cached_token()

            if token_info is None:
                self.init_spotify(True)
            else:
                new_token_info = self.oauth.refresh_access_token(token_info["refresh_token"])
                self.spotipy_token = new_token_info["access_token"]
                self.spotify._auth = self.spotipy_token

            self.print_with_timestamp("Refreshed Spotify token.")

            temp_current_track = self.parse_current_track_string(
                self.spotify.current_user_playing_track()
            )

            if self.current_track != temp_current_track:
                self.current_track = temp_current_track

                with open("spotify_now_playing.txt", "w+") as file:
                    if self.current_track is not None:
                        file.write(
                            "Listening to {}".format(
                                self.parse_current_track_string_for_overlay(
                                    self.spotify.current_user_playing_track()
                                )
                            )
                        )
                    else:
                        file.write("")

    def print_current_track_to_chat(self) -> None:
        """Announce the current track in chat."""
        if self.current_track is None:
            self.send_text_to_channel(CHANNEL, "Nothing is currently playing.")
        else:
            self.send_text_to_channel(CHANNEL, "Currently playing {}".format(self.current_track))
            self.print_with_timestamp(self.current_track)

    def search_for_spotify_song(self, query: str, username: str) -> None:
        """Search Spotify and list matching tracks."""
        if self.spotify is None:
            self.send_text_to_channel(CHANNEL, "Playlist functionality is currently off.")
        else:
            results = self.spotify.search(query, type="track", limit=5)

            if len(results["tracks"]["items"]) == 0:
                self.send_text_to_channel(CHANNEL, "{} No results found.".format(username))
            else:
                for result in results["tracks"]["items"]:
                    self.send_text_to_channel(
                        CHANNEL,
                        '"{}" by {}. CODE: {}'.format(
                            result["name"], result["artists"][0]["name"], result["id"]
                        ),
                    )

    def search_add_song(self, query: str, username: str) -> None:
        """Search Spotify and add a unique match."""
        if self.spotify is None:
            self.send_text_to_channel(
                CHANNEL, "{} Playlist functionality is currently off.".format(username)
            )
        else:
            results = self.spotify.search(query, type="track", limit=5)

            if len(results["tracks"]["items"]) == 1:
                self.add_track_to_playlist(results["tracks"]["items"][0]["id"], username)
            elif len(results["tracks"]["items"]) == 0:
                self.send_text_to_channel(CHANNEL, "{} No results found.".format(username))
            else:
                self.send_text_to_channel(
                    CHANNEL,
                    '{} Too many results returned. Please choose one of the following and use "!addsong" command or narrow your search criteria.'.format(
                        username
                    ),
                )

                for result in results["tracks"]["items"]:
                    self.send_text_to_channel(
                        CHANNEL,
                        '"{}" by {}. CODE: {}'.format(
                            result["name"], result["artists"][0]["name"], result["id"]
                        ),
                    )

    def add_track_to_playlist(self, track: str, username: str) -> None:
        """Add a track code to the configured playlist."""
        if self.spotify is None:
            self.send_text_to_channel(
                CHANNEL, "{} Playlist functionality is currently off.".format(username)
            )
        else:
            try:
                results = self.spotify.user_playlist_add_tracks(
                    user=SPOTIFY_USERNAME, playlist_id=SPOTIFY_PLAYLIST_ID, tracks=[track]
                )
            except:
                results = None

            if results is not None:
                self.send_text_to_channel(CHANNEL, "{} Added song to playlist.".format(username))
            else:
                self.send_text_to_channel(CHANNEL, "{} Invalid song code.".format(username))

    def unbench_kench_passive(self, channel: str, lowercase_text: str) -> None:
        """Respond to unbench-the-kench phrases."""
        unbench_kench = False
        kench_keys = sorted(Memes.UNBENCH_KENCH.keys())

        for key in kench_keys:
            if Memes.UNBENCH_KENCH[key].lower() in lowercase_text:
                unbench_kench = True

        if unbench_kench:
            key = random.randint(0, (len(kench_keys) - 1))
            self.send_text_to_channel(channel, Memes.UNBENCH_KENCH[kench_keys[key]] + " OSFrog")

    def command_unbench_kench(self, channel: str) -> None:
        """Post every unbench-the-kench response."""
        output_string = ""

        for key, value in Memes.UNBENCH_KENCH.items():
            output_string += value + " OSFrog "

        self.send_text_to_channel(channel, output_string.strip())

    def parse_line(self, line: str) -> None:
        """Parse one IRC line and dispatch any command."""
        # Split the line into 3 parts, using ":" as the delimiter
        split_line = line.split(":", 2)

        channel = self.get_channel_from_line(split_line[1])
        user_info = self.parse_line_tags(split_line[0])

        # Print the line with a time stamp and channel (if there is one) prepended
        if channel:
            log.debug("[%s] %s", channel, line)
        else:
            log.debug(line)

        # Declare a variable we'll use to check whether chat is idle or not
        reset_idle_chat_timer = True

        if len(split_line) == 2:
            if split_line[0] == "PING ":
                # If the server sent an AFK check, print the response and a timestamp, then send the response
                log.debug("PONG :tni.twitch.tv")
                self.send_encoded("PONG :tni.twitch.tv")
                reset_idle_chat_timer = False
        elif len(split_line) == 3:
            username = user_info.get("username", "").lower()
            split_line = line.split(
                "{}!{}@{}.tmi.twitch.tv PRIVMSG #{} :".format(
                    username, username, username, channel
                ),
                1,
            )
            text = split_line[1].strip()
            lowercase_text = text.lower()

            # Define commands for me
            if username == CHANNEL:
                reset_idle_chat_timer = False

                if lowercase_text == "@{} shut down".format(self.username):
                    self.power_down(username)
                elif lowercase_text == "!playlist on":
                    if self.spotify is None:
                        self.init_spotify()
                elif lowercase_text == "!playlist off":
                    self.spotify = None
                    self.current_track = None
                    self.oauth = None

            # Define commands for broadcaster
            if user_info.get("broadcaster", False):
                if lowercase_text == "@{} begone".format(self.username):
                    self.leave_channel(channel)
                    self.print_with_timestamp_and_channel(
                        channel,
                        'COMMAND: Exit Channel "{}" ({})'.format(channel, user_info["username"]),
                    )

            # Define commands for any user in any channel
            if channel and username != "":
                self.unbench_kench_passive(channel, lowercase_text)

                if lowercase_text == "!commands":
                    self.send_text_to_channel(
                        channel,
                        "!commands, !song, !addsong [Spotify Code], !searchsong [Search Criteria], !searchadd [Search Criteria], !unbench, !jebaited, !slownsteady, !sleeptest, !srstrouble, !clown",
                    )
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: COMMAND LIST ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!song":
                    self.print_current_track_to_chat()
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: CURRENT SONG ({})".format(user_info["username"])
                    )
                elif lowercase_text.startswith("!addsong"):
                    if " " in text:
                        track_code = text.split(" ", 1)[1].strip()
                        self.add_track_to_playlist(track_code, user_info["username"])
                        self.print_with_timestamp_and_channel(
                            channel,
                            "COMMAND: ADD SONG ({}, {})".format(user_info["username"], track_code),
                        )
                    else:
                        self.send_text_to_channel(
                            channel,
                            "{} Usage: !addsong [Spotify code]".format(user_info["username"]),
                        )
                elif lowercase_text.startswith("!searchsong"):
                    if " " in text:
                        query = text.split(" ", 1)[1].strip()
                        self.search_for_spotify_song(query, user_info["username"])
                        self.print_with_timestamp_and_channel(
                            channel,
                            "COMMAND: SEARCH SONG ({}, {})".format(user_info["username"], query),
                        )
                    else:
                        self.send_text_to_channel(
                            channel,
                            "{} Usage: !searchsong [search criteria]".format(user_info["username"]),
                        )
                elif lowercase_text.startswith("!searchadd"):
                    if " " in text:
                        query = text.split(" ", 1)[1].strip()
                        self.search_add_song(query, user_info["username"])
                        self.print_with_timestamp_and_channel(
                            channel,
                            "COMMAND: SEARCH AND ADD ({}, {})".format(user_info["username"], query),
                        )
                    else:
                        self.send_text_to_channel(
                            channel,
                            "{} Usage: !searchadd [search criteria]".format(user_info["username"]),
                        )
                elif lowercase_text == "!unbench":
                    self.command_unbench_kench(channel)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: UNBENCH THE KENCH ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!jebaited":
                    self.send_text_to_channel(channel, Memes.JEBAITED)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: JEBAITED ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!slownsteady":
                    self.send_text_to_channel(channel, Memes.SLOW_AND_STEADY)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: SLOW AND STEADY ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!lapras":
                    self.send_text_to_channel(channel, Memes.LAPRAS)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: LAPRAS ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!sleeptest":
                    self.send_text_to_channel(channel, Memes.SLEEP_TEST)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: SLEEP TEST ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!babblingbook":
                    self.send_text_to_channel(channel, Memes.BABBLING_BOOK)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: BABBLING BOOK ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!srstrouble":
                    self.send_text_to_channel(channel, Memes.SERIOUS_TROUBLE)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: SERIOUS TROUBLE ({})".format(user_info["username"])
                    )
                elif lowercase_text == "!clown":
                    self.send_text_to_channel(channel, Memes.OVERCLOWNFIDENCE)
                    self.print_with_timestamp_and_channel(
                        channel, "COMMAND: OVERCLOWNFIDENCE ({})".format(user_info["username"])
                    )
                elif channel in self.adventure_list:
                    adventure = self.adventure_list[channel]

                    if user_info["username"] in adventure.player_list:
                        player = adventure.player_list[user_info["username"]]

                        if lowercase_text == "!adventure commands":
                            self.send_text_to_channel(
                                channel,
                                "!adventure commands, !attack, !status, !inventory, !equipped, !equip [item name], !unequip [item name], !iteminfo [item name]",
                            )
                            self.print_with_timestamp_and_channel(
                                channel,
                                "COMMAND: Adventure Command List ({})".format(
                                    user_info["username"]
                                ),
                            )
                        elif lowercase_text == "!attack":
                            game_state = adventure.attack_phase(
                                player, adventure.boss_list[adventure.level_counter]
                            )

                            while len(game_state) > 0:
                                self.send_text_to_channel(channel, game_state.popleft())

                            self.print_with_timestamp_and_channel(
                                channel, "COMMAND: Attack! ({})".format(user_info["username"])
                            )
                        elif lowercase_text == "!status":
                            self.send_text_to_channel(channel, player.get_status())
                            self.print_with_timestamp_and_channel(
                                channel, "COMMAND: My Status ({})".format(user_info["username"])
                            )
                        elif lowercase_text == "!inventory":
                            self.send_text_to_channel(channel, player.get_inventory())
                            self.print_with_timestamp_and_channel(
                                channel, "COMMAND: My Inventory ({})".format(user_info["username"])
                            )
                        elif lowercase_text == "!equipped":
                            self.send_text_to_channel(channel, player.get_equipment())
                            self.print_with_timestamp_and_channel(
                                channel, "COMMAND: My Equipment ({})".format(user_info["username"])
                            )
                        elif lowercase_text.find("!equip") == 0:
                            if " " in lowercase_text:
                                item_name = lowercase_text.split(" ", 1)[1]
                                game_state = player.equip(item_name)
                                self.send_text_to_channel(channel, game_state)
                                self.print_with_timestamp_and_channel(
                                    channel,
                                    "COMMAND: Equip ({}, {})".format(
                                        user_info["username"], item_name
                                    ),
                                )
                        elif lowercase_text.find("!unequip") == 0:
                            if " " in lowercase_text:
                                item_name = lowercase_text.split(" ", 1)[1]
                                game_state = player.unequip(item_name)
                                self.send_text_to_channel(channel, game_state)
                                self.print_with_timestamp_and_channel(
                                    channel,
                                    "COMMAND: Unequip ({}, {})".format(
                                        user_info["username"], item_name
                                    ),
                                )
                        elif lowercase_text.find("!iteminfo") == 0:
                            if " " in lowercase_text:
                                item_name = lowercase_text.split(" ", 1)[1]
                                game_state = player.item_info(item_name)
                                self.send_text_to_channel(channel, game_state)
                                self.print_with_timestamp_and_channel(
                                    channel,
                                    "COMMAND: Item Info ({}, {})".format(
                                        user_info["username"], item_name
                                    ),
                                )

                    elif lowercase_text == "!join":
                        adventure.add_player(user_info["username"])
                        self.send_text_to_channel(
                            channel, "{} has joined the party!".format(user_info["username"])
                        )
                        self.print_with_timestamp_and_channel(
                            channel, "COMMAND: Join Adventure ({})".format(user_info["username"])
                        )

        if reset_idle_chat_timer:
            self.idle_chat_sleep_timer = datetime.datetime.now() + datetime.timedelta(
                minutes=random.randint(4, 15)
            )

    def monitor_chat(self) -> None:
        """Run the main read loop until every channel is left."""
        read_buffer = ""

        while len(self.channel_list) > 0:
            is_readable = [self.socket]
            is_writable = []
            is_error = []
            r, w, e = select.select(is_readable, is_writable, is_error, 1.0)

            if r:
                read_buffer = read_buffer + self.socket.recv(1024).decode()
                temp_buffer = read_buffer.split("\n")
                read_buffer = temp_buffer.pop()

                for line in temp_buffer:
                    self.parse_line(line)
            else:
                if self.spotify is not None:
                    self.update_spotify_token()
                    self.update_current_track()

                if self.bot_info_sleep_timer <= datetime.datetime.now():
                    self.bot_info_sleep_timer = datetime.datetime.now() + datetime.timedelta(
                        minutes=20
                    )
                    self.send_text_to_channel(CHANNEL, self.bot_info_message)

                if (
                    self.self_promotion_message
                    and self.self_promotion_sleep_timer <= datetime.datetime.now()
                ):
                    self.self_promotion_sleep_timer = datetime.datetime.now() + datetime.timedelta(
                        minutes=15
                    )
                    self.send_text_to_channel(CHANNEL, self.self_promotion_message)

                if self.idle_chat_sleep_timer <= datetime.datetime.now():
                    self.idle_chat_sleep_timer = datetime.datetime.now() + datetime.timedelta(
                        minutes=random.randint(4, 15)
                    )
                    self.send_text_to_channel(
                        CHANNEL, self.idle_messages[random.randint(0, len(self.idle_messages) - 1)]
                    )

                for channel in self.adventure_list:
                    adventure = self.adventure_list[channel]

                    if adventure.location == Adventure.Locations.town:
                        if datetime.datetime.now() >= (
                            adventure.location_time + datetime.timedelta(minutes=5)
                        ):
                            adventure.go_to_location(Adventure.Locations.dungeon)
                    elif adventure.location == Adventure.Locations.dungeon:
                        boss = adventure.boss_list[adventure.level_counter]

                        if boss.last_attack_time is None or datetime.datetime.now() >= (
                            boss.last_attack_time + datetime.timedelta(0, 5)
                        ):
                            boss.last_attack_time = datetime.datetime.now()

                            for username in adventure.player_list:
                                player = adventure.player_list[username]
                                if player.current_health > 0:
                                    game_state = adventure.attack_phase(boss, player)
                                    self.send_text_to_channel(channel, game_state.popleft())

        self.print_with_timestamp("See ya!")
