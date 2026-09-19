"""Cache TTL per /apple-music/* endpoint (cache.py, keyed on the validated
params — marshmallow fills the defaults, so `?page=1` and no `page` share a
row).

Tiers follow how fast Apple Music moves each surface: catalog entities
(songs, albums, artists, labels) change rarely, editorial playlists are
refreshed a few times a week, charts update daily (Daily Top 100 around
midnight per region) and the Browse/Radio pages every few hours.
"""
from datetime import timedelta

# --- catalog entities -------------------------------------------------------------
SONG_CACHE = timedelta(days=3)
ALBUM_CACHE = timedelta(days=1)            # prereleases flip to released, track lists grow
ARTIST_CACHE = timedelta(hours=12)         # latest release / top songs move
ARTIST_LIST_CACHE = timedelta(hours=12)
PLAYLIST_CACHE = timedelta(hours=3)        # editorial playlists are re-cut often
VIDEO_CACHE = timedelta(days=1)
LABEL_CACHE = timedelta(hours=12)
CURATOR_CACHE = timedelta(hours=6)
STATION_CACHE = timedelta(minutes=30)      # live stations change what is on air

# --- search -------------------------------------------------------------------------
AUTOCOMPLETE_CACHE = timedelta(days=1)
SEARCH_CACHE = timedelta(hours=6)

# --- charts / editorial ----------------------------------------------------------------
CHART_CACHE = timedelta(hours=1)
CHART_LIST_CACHE = timedelta(hours=12)
BROWSE_CACHE = timedelta(hours=1)
RADIO_CACHE = timedelta(minutes=15)

# --- reference ------------------------------------------------------------------------
GENRES_CACHE = timedelta(days=7)
GENRE_PAGE_CACHE = timedelta(hours=6)
COUNTRIES_CACHE = timedelta(days=7)
