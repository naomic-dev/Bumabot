# Bumabot

> A Twitch chat bot built directly on the IRC protocol, with timed messages, Spotify now-playing integration, and an experimental dungeon-crawler module.

![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Spotipy](https://img.shields.io/badge/spotipy-2.19-1DB954?logo=spotify&logoColor=white)
![CI](https://github.com/naomic-dev/Bumabot/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

Bumabot was the chat bot for my Twitch channel. Instead of hiding the protocol behind a client library, it speaks Twitch IRC directly: it negotiates capabilities, parses user tags, joins and leaves channels, answers commands, and sends scheduled messages. It also tracks what I was listening to on Spotify and lets viewers search for tracks or add them to a shared playlist.

This repository is a cleaned-up reference version. Channel-specific responses and personal references have been removed, and the adventure module is intentionally marked experimental. The bot runs from a local `.env` file; no credentials are committed.

## Features

- **Direct Twitch IRC client** — CAP negotiation, OAuth login, channel join/part, PING/PONG keepalive, and IRC tag parsing for display names, badges, and colors.
- **Command handling** — chat commands for the bot, the channel owner, and the broadcaster.
- **Timed messages** — periodic command hints for newcomers and optional idle-chat prompts.
- **Spotify integration** — current-track announcements, track search, and playlist additions, with token refresh and a `spotify_now_playing.txt` overlay file.
- **Data-driven responses** — meme and shoutout text lives in `Memes.py`, not inside the command router.
- **Structured logging** — level-controlled logs with timestamps and module names; set `LOG_LEVEL` to `DEBUG` to see raw IRC traffic.
- **Experimental adventure module** — a turn-based dungeon crawler with parties, bosses, loot, equipment, and death/revival rules.

## Commands

| Command | Who | Description |
| --- | --- | --- |
| `!commands` | Everyone | List the available commands. |
| `!song` | Everyone | Announce the current Spotify track. |
| `!searchsong <query>` | Everyone | Search Spotify and list matching track codes. |
| `!addsong <code>` | Everyone | Add a track code to the configured playlist. |
| `!searchadd <query>` | Everyone | Search Spotify and add a single match. |
| `!unbench` | Everyone | Post the full "unbench the kench" collection. |
| `!jebaited`, `!slownsteady`, `!lapras`, `!sleeptest`, `!babblingbook`, `!srstrouble`, `!clown` | Everyone | Post a themed chat response. |
| `!adventure commands`, `!attack`, `!status`, `!inventory`, `!equipped`, `!equip <item>`, `!unequip <item>`, `!iteminfo <item>` | Adventure players | Interact with the experimental adventure module. |
| `@<bot> shut down` | Channel owner | Leave every channel and stop the bot. |
| `!playlist on` / `!playlist off` | Channel owner | Enable or disable Spotify features. |
| `@<bot> begone` | Broadcaster | Leave the current channel. |

The bot also watches chat for "unbench the kench" phrases and responds passively.

## Architecture

```
Run.py          Entry point
ChatBot.py      IRC socket, command routing, timed messages, Spotify
Adventure.py    Experimental dungeon-crawler engine
Memes.py        Chat response constants
Settings.py     Environment-based configuration
logging_config.py  Level-controlled logging setup
pyproject.toml     Black formatting configuration
tests/
  test_adventure.py            Combat, loot, equipment, revival
  test_chatbot.py              IRC tags and command routing (fake socket)
  test_settings.py             Environment validation
.github/workflows/ci.yml       Test matrix (Python 3.8, 3.10, 3.12)
```

- `ChatBot` owns the socket and the main read loop. `select` keeps the loop responsive while scheduled messages and Spotify polling run between incoming lines.
- Command parsing splits Twitch IRC lines into tags, prefix, and message body. Tags provide the display name, badge list, moderator status, and subscriber status.
- Spotify access uses a cached OAuth token, refreshed hourly; the currently playing track is mirrored into `spotify_now_playing.txt` for an OBS overlay.
- `Adventure` is a separate state machine with characters, items, locations, and scheduled boss attacks. It is not currently started by a chat command; see the roadmap.

## Requirements

- Python 3.8+
- A Twitch account and a chat OAuth token from <https://twitchapps.com/tmi/>
- Optional: a Spotify application and a playlist if you want the Spotify features

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create your environment file:

   ```bash
   cp .env.example .env
   ```

3. Fill in the required Twitch values:

   | Variable | Description |
   | --- | --- |
   | `TWITCH_OAUTH_TOKEN` | Chat token from twitchapps.com/tmi. The `oauth:` prefix is added if omitted. |
   | `TWITCH_BOT_USERNAME` | The bot account's username (lowercase). |
   | `TWITCH_CHANNEL` | The channel to join (lowercase). |
   | `TWITCH_IRC_HOST` | IRC host. Defaults to `irc.chat.twitch.tv`. |
   | `TWITCH_IRC_PORT` | IRC port. Defaults to `6667`. |
   | `TWITCH_USERNAME_COLOR` | Chat color set after joining. Defaults to `blue`. |
   | `SELF_PROMOTION_MESSAGE` | Optional timed message. Leave empty to disable. |
   | `LOG_LEVEL` | Logging threshold: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Defaults to `INFO`. |

4. Optional Spotify setup:

   - Create an application at <https://developer.spotify.com/dashboard>.
   - Add `http://localhost/` as a redirect URI.
   - Fill in `SPOTIFY_USERNAME`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_PLAYLIST_ID`.
   - On first start the bot prints an authorization URL and asks for the code; the token is cached in `.cache-<username>`.

5. Run:

   ```bash
   python Run.py
   ```

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The suite uses only the standard library and a fake IRC socket, so it needs no network access or Twitch credentials. It covers IRC tag parsing, command routing (including the Spotify-disabled paths), and the adventure engine's combat, loot, equipment, and revival rules. CI runs the same suite on Python 3.8, 3.10, and 3.12. Formatting uses Black with the configuration in `pyproject.toml`.

## Design notes

- **Raw IRC instead of a library.** Twitch chat is just IRC with tags. Handling `CAP REQ`, `PASS`, `NICK`, `JOIN`, `PRIVMSG`, and `PING` directly made the protocol visible and kept the dependency surface small.
- **One socket, many timers.** The main loop uses `select` with a one-second timeout, so scheduled messages, Spotify token refreshes, and boss attacks share the same thread as chat parsing.
- **Spotify is optional.** If the Spotify values are blank, the bot skips OAuth and reports that playlist features are off instead of failing at startup.
- **Logging instead of print.** Command activity is logged at `INFO`; raw IRC traffic and combat rolls are `DEBUG`.
- **Adventure is data-driven.** Bosses, drops, and items are plain data in `Adventure.py`; the engine handles combat, credit for kills, equipment, and party wipes.

## Known limitations

- **The adventure module is incomplete.** No command currently creates an adventure, so its chat commands are unreachable; the engine has unit tests, but the full flow is not playable from chat.
- **Plain TCP on port 6667.** Twitch also exposes TLS on 6697; switching to `ssl` is on the roadmap.
- **Pinned Spotipy API.** The integration targets Spotipy 2.19; newer releases removed `prompt_for_user_token` and `user_playlist_add_tracks`.
- **Live integration is untested.** The test suite uses a fake IRC socket and a disabled Spotify client; it does not connect to Twitch or Spotify.

## Roadmap

- [ ] Start an adventure from chat and finish the dungeon flow.
- [ ] Move to TLS on port 6697.
- [ ] Update the Spotify integration to the current Spotipy API.

## License

MIT — see [LICENSE](LICENSE).
