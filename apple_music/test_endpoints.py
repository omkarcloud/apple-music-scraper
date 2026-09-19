"""Live endpoint smoke tests: one call per /apple-music/* route against a
running service, with example values proven to return data (2026-09-19).
The listing tooling (derive_facts.py) also reads these calls as each
route's working example.

Skipped unless APPLE_MUSIC_BASE points at a running service:

    ONLY_SCRAPER=apple-music python run.py            # or any bottle runner
    APPLE_MUSIC_BASE=http://127.0.0.1:6002 python -m pytest apple_music/test_endpoints.py -q
"""
import os

import pytest

BASE = os.environ.get("APPLE_MUSIC_BASE", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="set APPLE_MUSIC_BASE to run live endpoint tests")


def call(path, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=180)
    assert resp.status_code == 200, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


# ---- search ------------------------------------------------------------------------

def test_search():
    assert call("/apple-music/search/auto-complete", query="taylor")["top_results"]
    assert call("/apple-music/search/all", query="taylor swift")["songs"]
    assert call("/apple-music/search/songs", query="anti-hero")["songs"]
    assert call("/apple-music/search/albums", query="midnights")["albums"]
    assert call("/apple-music/search/artists", query="taylor swift")["artists"]
    assert call("/apple-music/search/playlists", query="workout")["playlists"]
    assert call("/apple-music/search/music-videos", query="taylor swift")["music_videos"]
    assert call("/apple-music/search/stations", query="hits")["stations"]
    assert call("/apple-music/search/curators", query="hits")["curators"]
    assert call("/apple-music/search/labels", query="def jam")["labels"]


# ---- songs / albums / videos ---------------------------------------------------------

def test_songs_albums_videos():
    assert call("/apple-music/songs/details", song="1649434293")["isrc"] == "USUG12205736"
    assert call("/apple-music/songs/batch", songs="1649434293,1440841367")["songs"]
    assert call("/apple-music/albums/details", album="1649434004")["tracks"]
    assert call("/apple-music/albums/related", album="1649434004")["more_by_artist"]
    assert call("/apple-music/music-videos/details", video="1650836460")["name"]


# ---- artists -----------------------------------------------------------------------

def test_artists():
    assert call("/apple-music/artists/details", artist="159260351")["top_songs"]
    assert call("/apple-music/artists/top-songs", artist="159260351")["songs"]
    assert call("/apple-music/artists/albums", artist="159260351")["albums"]
    assert call("/apple-music/artists/music-videos", artist="159260351")["music_videos"]
    assert call("/apple-music/artists/playlists", artist="159260351")["playlists"]
    assert call("/apple-music/artists/similar", artist="159260351")["artists"]


# ---- playlists -----------------------------------------------------------------------

def test_playlists():
    assert call("/apple-music/playlists/details", playlist="pl.3950454ced8c45a3b0cc693c2a7db97b")["tracks"]
    assert call("/apple-music/playlists/tracks", playlist="pl.3950454ced8c45a3b0cc693c2a7db97b")["tracks"]


# ---- charts ------------------------------------------------------------------------

def test_charts():
    assert call("/apple-music/charts/top-songs", country="us")["songs"]
    assert call("/apple-music/charts/top-albums", country="us")["albums"]
    assert call("/apple-music/charts/top-playlists", country="us")["playlists"]
    assert call("/apple-music/charts/top-music-videos", country="us")["music_videos"]
    assert call("/apple-music/charts/daily-top-100", region="us")["songs"]
    assert call("/apple-music/charts/daily-top-100-list", lang="en-US")["charts"]
    assert call("/apple-music/charts/city-top-25", city="los angeles")["songs"]
    assert call("/apple-music/charts/city-charts-list", lang="en-US")["charts"]


# ---- browse / radio ----------------------------------------------------------------------

def test_browse():
    assert call("/apple-music/browse", country="us")["sections"]
    assert call("/apple-music/browse/section", section="6813319894")["items"]
    assert call("/apple-music/browse/new-releases", country="us")["items"]
    assert call("/apple-music/browse/recent-releases", country="us")["items"]
    assert call("/apple-music/browse/best-new-songs", country="us")["items"]
    assert call("/apple-music/browse/trending-songs", country="us")["items"]
    assert call("/apple-music/browse/coming-soon", country="us")["items"]
    assert call("/apple-music/browse/updated-playlists", country="us")["items"]
    assert call("/apple-music/browse/popular", country="us")["items"]
    assert call("/apple-music/browse/dj-mixes", country="us")["items"]
    assert call("/apple-music/radio", country="us")["sections"]


# ---- stations / genres / labels / curators / countries -------------------------------------

def test_catalog():
    assert call("/apple-music/stations/live", country="us")["stations"]
    assert call("/apple-music/stations/details", station="ra.1498155548")["name"]
    assert call("/apple-music/genres", country="us")["genres"]
    assert call("/apple-music/genres/details", genre="pop")["sections"]
    assert call("/apple-music/labels/details", label="1556733255")["latest_releases"]
    assert call("/apple-music/labels/releases", label="1556733255")["albums"]
    assert call("/apple-music/curators/details", curator="1526756058")["playlists"]
    assert call("/apple-music/curators/playlists", curator="1526756058")["playlists"]
    assert call("/apple-music/countries", lang="en-US")["countries"]
