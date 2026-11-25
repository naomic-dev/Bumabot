"""Environment-backed configuration for the bot."""

import os

from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            "Missing required environment variable: {}. "
            "Copy .env.example to .env and fill it in.".format(name)
        )

    return value


HOST = os.getenv("TWITCH_IRC_HOST", "irc.chat.twitch.tv")
PORT = int(os.getenv("TWITCH_IRC_PORT", "6697"))
USERNAME_COLOR = os.getenv("TWITCH_USERNAME_COLOR", "blue")
USE_TLS = os.getenv("TWITCH_IRC_TLS", "true").lower() in ("1", "true", "yes", "on")

# The TMI token already includes the oauth: prefix; add it if it was omitted.
PASS = required("TWITCH_OAUTH_TOKEN")

if not PASS.startswith("oauth:"):
    PASS = "oauth:" + PASS

NICK = required("TWITCH_BOT_USERNAME").lower()
CHANNEL = required("TWITCH_CHANNEL").lower()

# Optional timed message. Leave empty to disable self-promotion.
SELF_PROMOTION_MESSAGE = os.getenv("SELF_PROMOTION_MESSAGE", "")

# Spotify is optional; all of these values are required to enable it.
SPOTIFY_USERNAME = os.getenv("SPOTIFY_USERNAME", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost/")
SPOTIFY_PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID", "")

SPOTIFY_ENABLED = all(
    [
        SPOTIFY_USERNAME,
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET,
        SPOTIFY_PLAYLIST_ID,
    ]
)
