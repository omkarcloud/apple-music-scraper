"""Configuration for the Apple Music Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT                port the API listens on (default 8000)
    APPLE_MUSIC_PROXY   proxy URL for every request, e.g. http://user:pass@host:port
                        (default: none — direct). Apple Music runs no bot
                        protection and every country's catalog is reachable
                        from any IP, so you very likely don't need this. Set
                        it only if you start seeing failures at high volume.
    APPLE_MUSIC_TOKEN   pin the Apple Music web player token by hand
                        (default: none — the scraper reads it from
                        music.apple.com itself and refreshes it when it expires)

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

APPLE_MUSIC_PROXY = os.environ.get("APPLE_MUSIC_PROXY") or None
APPLE_MUSIC_TOKEN = os.environ.get("APPLE_MUSIC_TOKEN") or None


def apple_music_proxy():
    """Proxy URL for a new session (None = direct)."""
    return os.environ.get("APPLE_MUSIC_PROXY") or None
