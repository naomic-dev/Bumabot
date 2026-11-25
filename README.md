# Bumabot

> A Twitch chat bot built directly on the IRC protocol, with timed messages, Spotify now-playing integration, and a small dungeon-crawler game.

![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Spotipy](https://img.shields.io/badge/spotipy-2.23-1DB954?logo=spotify&logoColor=white)
![CI](https://github.com/naomic-dev/Bumabot/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

Bumabot was the chat bot for my Twitch channel. Instead of hiding the protocol behind a client library, it speaks Twitch IRC directly: it negotiates capabilities, parses user tags, joins and leaves channels, answers commands, and sends scheduled messages. It also tracks what I was listening to on Spotify and lets viewers search for tracks or add them to a shared playlist.

This repository is a cleaned-up reference version. Channel-specific responses and personal references have been removed. The adventure module is a minimal but playable loop. The bot runs from a local `.env` file; no credentials are committed.

## Features

- **Direct Twitch IRC client** — TLS on port 6697, CAP negotiation, OAuth login, channel join/part, PING/PONG keepalive, and IRC tag parsing for display names, badges, and colors.
- **Command handling** — chat commands for the bot, the channel owner, and the broadcaster.
- **Timed messages** — periodic command hints for newcomers and optional idle-chat prompts.
- **Spotify integration** — current-track announcements, track search, and playlist additions, with token refresh and a `spotify_now_playing.txt` overlay file.
- **Data-driven responses** — meme and shoutout text lives in `Memes.py`, not inside the command router.
- **Structured logging** — level-controlled logs with timestamps and module names; set `LOG_LEVEL` to `DEBUG` to see raw IRC traffic.
- **Adventure module** — a playable turn-based dungeon crawler with parties, bosses, loot, equipment, and death/revival rules.

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
| `!join` | Everyone | Join the active adventure. |
| `!adventure commands`, `!attack`, `!status`, `!inventory`, `!equipped`, `!equip <item>`, `!unequip <item>`, `!iteminfo <item>` | Adventure players | Interact with the adventure. |
| `!adventure start` | Channel owner | Start a town-phase adventure with a 5-minute join window. |
| `!adventure go` | Channel owner | Send the party into the dungeon immediately. |
| `!adventure stop` | Channel owner | End the channel's adventure. |
| `@<bot> shut down` | Channel owner | Leave every channel and stop the bot. |
| `!playlist on` / `!playlist off` | Channel owner | Enable or disable Spotify features. |
| `@<bot> begone` | Broadcaster | Leave the current channel. |

The bot also watches chat for "unbench the kench" phrases and responds passively.

## Demo

Illustrative transcript; names, tracks, and damage rolls are placeholders.

```text
<Viewer> !commands
<Bumabot> !commands, !song, !addsong [Spotify Code], !searchsong [Search Criteria], !searchadd [Search Criteria], !unbench, !jebaited, !slownsteady, !lapras, !sleeptest, !babblingbook, !srstrouble, !clown, !join (adventure)

<Viewer> !song
<Bumabot> Currently playing "One More Time" by Daft Punk https://open.spotify.com/track/...

<Viewer> !searchsong daft punk
<Bumabot> "Around the World" by Daft Punk. CODE: 2i1f2...
<Bumabot> "One More Time" by Daft Punk. CODE: 3n3f4...

<Viewer> !addsong 3n3f4...
<Bumabot> Added song to playlist.

<Viewer> !unbench
<Bumabot> UNROLL THE TADPOLE OSFrog UNCLOG THE FROG OSFrog ...
```

```text
<Streamer> !adventure start
<Bumabot> The party finds itself in a peaceful mountain town. After a brief rest to rally their strength, the party will depart.
<Bumabot> Adventure started! Type !join to join the party. The channel owner can use !adventure go to enter the dungeon now.

<Viewer> !join
<Bumabot> Viewer has joined the party!

<Streamer> !adventure go
<Bumabot> The party has entered a dungeon. A Rat has appeared.

<Viewer> !attack
<Bumabot> Viewer attacked Rat for 3 damage. Rat has died.
<Bumabot> Viewer got a Clump of Rat Fur!
<Bumabot> A Large Rat has appeared.

<Bumabot> Large Rat attacked Viewer for 1 damage.

<Viewer> !status
<Bumabot> Viewer Status: OK, HP: 9/10, ATK: 1, SPD: 1, Kills: 1, Deaths: 0

<Viewer> !inventory
<Bumabot> Viewer Inventory (1): #1 Clump of Rat Fur

<Streamer> !adventure stop
<Bumabot> Adventure stopped.
```

## Architecture

```
Run.py          Entry point
ChatBot.py      IRC socket (TLS), command routing, timed messages, Spotify
Adventure.py    Minimal dungeon-crawler engine
Memes.py        Chat response constants
Settings.py     Environment-based configuration
logging_config.py  Level-controlled logging setup
pyproject.toml     Black and Ruff configuration
requirements-dev.txt  Black and Ruff versions used by CI
tests/
  test_adventure.py            Combat, loot, equipment, revival
  test_chatbot.py              IRC tags and command routing (fake socket)
  test_settings.py             Environment validation
.github/workflows/ci.yml       Tests and lint (Python 3.8, 3.10, 3.12)
```

- `ChatBot` owns the socket and the main read loop. `select` keeps the loop responsive while scheduled messages and Spotify polling run between incoming lines.
- Command parsing splits Twitch IRC lines into tags, prefix, and message body. Tags provide the display name, badge list, moderator status, and subscriber status.
- Spotify access uses a cached OAuth token, refreshed hourly; the currently playing track is mirrored into `spotify_now_playing.txt` for an OBS overlay.
- `Adventure` is a separate state machine with characters, items, locations, and scheduled boss attacks. The channel owner starts it with `!adventure start`; the loop advances the town phase and boss attacks.

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
   | `TWITCH_IRC_PORT` | IRC port. Defaults to `6697`. |
   | `TWITCH_IRC_TLS` | Wrap the IRC connection in TLS. Defaults to `true`; set `false` only for a local test server. |
   | `TWITCH_USERNAME_COLOR` | Chat color set after joining. Defaults to `blue`. |
   | `SELF_PROMOTION_MESSAGE` | Optional timed message. Leave empty to disable. |
   | `LOG_LEVEL` | Logging threshold: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Defaults to `INFO`. |

   TLS is on by default. If your `.env` still sets `TWITCH_IRC_PORT=6667`, move it to `6697`; set `TWITCH_IRC_TLS=false` only when testing against a local server.

4. Optional Spotify setup:

   - Create an application at <https://developer.spotify.com/dashboard>.
   - Add `http://localhost/` as a redirect URI.
   - Fill in `SPOTIFY_USERNAME`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_PLAYLIST_ID`. The username is used as the local token cache label.
   - On first start the bot prints an authorization URL and asks for the full URL you were redirected to; the token is cached in `.cache-<username>`.

5. Run:

   ```bash
   python Run.py
   ```

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The suite uses only the standard library and a fake IRC socket, so it needs no network access or Twitch credentials. It covers IRC tag parsing, command routing (including the Spotify-disabled paths), and the adventure engine's combat, loot, equipment, and revival rules. CI runs the same suite on Python 3.8, 3.10, and 3.12, and a separate lint job runs Black and Ruff.

Formatting and lint checks:

```bash
pip install -r requirements-dev.txt
black --check .
ruff check .
```

## Design notes

- **Raw IRC instead of a library.** Twitch chat is just IRC with tags. Handling `CAP REQ`, `PASS`, `NICK`, `JOIN`, `PRIVMSG`, and `PING` directly made the protocol visible and kept the dependency surface small.
- **One socket, many timers.** The main loop uses `select` with a one-second timeout, so scheduled messages, Spotify token refreshes, and boss attacks share the same thread as chat parsing.
- **Spotify is optional.** If the Spotify values are blank, the bot skips OAuth and reports that playlist features are off instead of failing at startup.
- **Logging instead of print.** Command activity is logged at `INFO`; raw IRC traffic and combat rolls are `DEBUG`.
- **TLS by default.** Port 6697 protects the OAuth token and chat traffic; `TWITCH_IRC_TLS=false` is only for a local test server.
- **Adventure is data-driven.** Bosses, drops, and items are plain data in `Adventure.py`; the engine handles combat, credit for kills, equipment, and party wipes.

## Known limitations

- **The adventure loop is minimal.** It has a town phase, boss fights, loot, and revival, but limited content and balance.
- **Live integration is untested.** The test suite uses a fake IRC socket and mocked Spotify clients; it does not connect to Twitch or Spotify.

## Roadmap

- [ ] Expand the adventure with more bosses, items, and balance tuning.
- [ ] Add screenshots and a short demo recording.

## License

MIT — see [LICENSE](LICENSE).
