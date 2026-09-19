"""Offline tests for the Apple Music scraper — no network.

Every fixture in apple_music/fixtures/ is a real amp-api payload captured
on 2026-09-19 (lists trimmed to a few items; editorial groupings keep their
full shelf layout). The assertions pin the field mapping decoded from live
data, so a silent upstream rename shows up here rather than as nulls in a
customer's response. Endpoint tests swap the transport for a fake that
serves fixtures by path.

    python -m pytest apple_music/test_parsers.py -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apple_music import fetch, refs, schemas               # noqa: E402
from apple_music import parsers as P                       # noqa: E402
from schema_fields import load_query                       # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def first(name):
    return load(name)["data"][0]


# ---- refs / schemas ----------------------------------------------------------------

def test_song_ref_forms():
    assert refs.resolve_song("1440841367") == {"id": "1440841367", "country": None}
    assert refs.resolve_song("uscm51600061") == {"isrc": "USCM51600061"}
    assert refs.resolve_song("https://music.apple.com/gb/album/views/1440841363?i=1440841367") == \
        {"id": "1440841367", "country": "gb"}
    assert refs.resolve_song("https://music.apple.com/us/song/keep-the-family-close/1440841367")["id"] == "1440841367"


def test_album_artist_and_other_refs():
    assert refs.resolve_album("00602547943491") == {"upc": "00602547943491"}
    assert refs.resolve_album("music.apple.com/us/album/views/1440841363")["id"] == "1440841363"
    assert refs.resolve_artist("https://itunes.apple.com/us/artist/drake/id271256") == {"id": "271256", "country": "us"}
    assert refs.resolve_playlist("pl.f4d106fed2bd41149aaacabb233eb5eb")["id"] == "pl.f4d106fed2bd41149aaacabb233eb5eb"
    assert refs.resolve_station("https://music.apple.com/us/station/apple-music-1/ra.978194965")["id"] == "ra.978194965"
    assert refs.resolve_genre("Rock") == {"id": None, "name": "Rock"}
    assert refs.resolve_genre("21") == {"id": "21", "name": None}


@pytest.mark.parametrize("resolver, bad", [
    (refs.resolve_artist, "https://open.spotify.com/artist/1"),
    (refs.resolve_artist, "drake"),
    (refs.resolve_artist, "https://music.apple.com/us/album/views/1440841363"),
    (refs.resolve_song, "999999999999"),
    (refs.resolve_playlist, "12345"),
])
def test_refs_reject_bad_input(resolver, bad):
    with pytest.raises(ValueError):
        resolver(bad)


def test_schemas_validate_and_default():
    data, err = load_query(schemas.ArtistAlbumsSchema, {"artist": "271256", "type": "Singles"})
    assert err is None and data["type"] == "singles" and data["page"] == 1 and data["limit"] == 20
    data, err = load_query(schemas.SongBatchSchema, {"songs": "1440841367, https://music.apple.com/us/song/x/1440841368,1440841367"})
    assert data["songs"] == ["1440841367", "1440841368"]
    data, err = load_query(schemas.DailyTop100Schema, {})
    assert data["region"] == "global"
    _, err = load_query(schemas.SearchSchema, {"query": "x", "typo": "1"})
    assert "typo" in err["errors"]
    _, err = load_query(schemas.SearchSchema, {"query": "x", "limit": "51"})
    assert "limit" in err["errors"]


# ---- value helpers -----------------------------------------------------------------

def test_value_helpers():
    assert P.duration_text(328910) == "5:28"          # the player truncates
    assert P.duration_text(3725000) == "1:02:05"
    assert P.human_date("October 24, 1986") == "1986-10-24"
    assert P.human_date("1986年10月24日") == "1986-10-24"
    assert P.human_date("1986") == "1986"
    assert P.iso_datetime("2026-09-19T07:42:19Z") == "2026-09-19T07:42:19Z"
    assert P.strip_html("A <i>b</i><br/>c&amp;d") == "A b\nc&d"
    assert P.snake("motionDetailSquare") == "motion_detail_square"
    assert P.snake("lossy-stereo") == "lossy_stereo"
    art = P.artwork({"url": "https://x/{w}x{h}bb.jpg", "width": 1000, "height": 800, "bgColor": "46535d"})
    assert art == {"link": "https://x/1000x800bb.jpg", "template_link": "https://x/{w}x{h}bb.jpg",
                   "width": 1000, "height": 800, "background_color": "#46535d"}
    assert P.artwork(None) is None


# ---- resources ---------------------------------------------------------------------

def test_song():
    s = P.song(first("song"))
    assert s["id"] == "1440841367" and s["name"] == "Keep the Family Close"
    assert s["album_id"] == "1440841363" and s["isrc"] == "USCM51600061"
    assert s["duration_ms"] == 328910 and s["duration"] == "5:28"
    assert s["is_explicit"] is True and s["has_time_synced_lyrics"] is True
    assert s["audio_traits"] == ["lossless", "lossy_stereo"]
    assert s["preview_link"].endswith(".m4a") and s["lyrics_excerpt"]
    assert "extendedAssetUrls" not in json.dumps(s) and "playParams" not in json.dumps(s)


def test_album():
    a = P.album(first("album"))
    assert a["name"] == "Views" and a["upc"] == "00602547943491" and a["release_type"] == "album"
    assert a["record_label"] and a["copyright"].startswith("℗")
    assert a["description"]["full"] and "<i>" not in a["description"]["full"]
    tracks = P.rel(first("album"), "tracks")
    assert tracks and P.items(tracks, typed=True)[0]["type"] == "song"


def test_artist():
    a = P.artist(first("artist"))
    assert a["name"] == "Drake" and a["origin"] == "Toronto, Ontario, Canada"
    assert a["born_or_formed"] == "1986-10-24" and a["is_group"] is False
    assert a["bio"] and "<" not in a["bio"]
    assert a["editorial_artwork"] and a["motion_artwork"]
    obj = first("artist")
    assert P.view_title(obj, "top-songs") == "Top Songs"
    assert P.items(P.view(obj, "top-songs"))[0]["isrc"]
    more = P.items(P.view(obj, "more-to-see"), typed=True)
    assert {m["type"] for m in more} <= {"uploaded_video", "music_movie"}


def test_playlist_and_curator():
    obj = first("playlist")
    p = P.playlist(obj)
    assert p["id"].startswith("pl.") and p["playlist_type"] == "editorial"
    assert p["track_count"] and p["last_modified_at"].endswith("Z")
    c = P.curator(P.rel(obj, "curator")[0])
    assert c["curator_type"] == "apple" and c["name"]
    ext = P.curator(first("curator"))
    assert ext["curator_type"] == "external"


def test_video_label_station_genre_country():
    v = P.music_video(first("music_video"))
    assert v["isrc"] and v["has_4k"] in (True, False) and v["preview"]["video_link"]
    lab = P.label(first("label"))
    assert lab["name"] and lab["description"]["full"]
    st = P.station(first("station"))
    assert st["id"] == "ra.978194965" and st["is_live"] is True and st["kind"] == "streaming"
    g = P.genre(load("genres")["data"][1])
    assert g["parent_id"] == "34"
    c = P.item(load("storefronts")["data"][0], typed=False)
    assert c["country_code"] == "DZ" and "link" not in c


def test_unknown_resource_type_does_not_crash():
    out = P.item({"id": "1", "type": "brand-new-type", "attributes": {"name": "X", "url": "https://u"}})
    assert out == {"type": "brand_new_type", "id": "1", "name": "X", "link": "https://u"}
    assert P.item(None) is None
    assert P.song({"id": "1"})["name"] is None                     # partial payload


# ---- editorial pages -----------------------------------------------------------------

def test_browse_grouping():
    sections, links = P.grouping_sections(load("browse"))
    titles = [s["title"] for s in sections]
    assert titles[0] == "Featured" and "Best New Songs" in titles
    featured = sections[0]["items"][0]
    assert "promo_badge" in featured and featured["type"]
    best = next(s for s in sections if s["title"] == "Best New Songs")
    assert best["content_types"] == ["song"] and best["see_all_id"]
    assert links and links[0]["link"].startswith("https://")


def test_radio_and_curator_page():
    sections, _ = P.grouping_sections(load("radio"))
    assert sections and all(s["items"] for s in sections)
    show = first("show_curator")
    grouping = show["relationships"]["grouping"]["data"]
    shelves, _ = P.grouping_sections({"data": grouping})
    assert shelves and shelves[0]["title"]


def test_room_info():
    info = P.room_info(first("room"))
    assert info["title"] == "New This Week" and info["default_sort"] == "featured"
    assert set(info["sort_options"]) == {"name", "release-date", "featured"}


def test_pagination_block():
    assert P.pagination(2, 20, True) == {"page": 2, "items_per_page": 20, "total_pages": 3, "total_count": None}
    assert P.pagination(3, 20, False)["total_pages"] == 3


# ---- transport helpers -------------------------------------------------------------------

def test_pick_token_takes_the_web_player_jwt():
    import base64

    def jwt(payload):
        enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        return f"{enc({'typ': 'JWT', 'alg': 'ES256', 'kid': 'WebPlayKid'})}.{enc(payload)}.{'x' * 40}"
    other, player = jwt({"iss": "M62YD85FTQ", "exp": 1}), jwt({"iss": "AMPWebPlay", "exp": 2})
    assert fetch.pick_token(f'a="{other}";b="{player}"') == player
    assert fetch.pick_token("no tokens") is None


def test_default_extend_is_merged():
    q = fetch._with_extend("/v1/catalog/us/artists/1", {"extend": "artistBio"})
    assert q["extend"].split(",")[0] == "artistBio" and "trackCount" in q["extend"]
    assert fetch._with_extend("/v1/storefronts", {}) == {}


def test_not_found_message():
    assert fetch.not_found_message("/v1/catalog/us/songs/123") == "song 123 not found in the US catalog"
    assert fetch.not_found_message("/v1/editorial/in/rooms/9/contents") == "section 9 not found in the IN catalog"


# ---- endpoints over a fake transport ---------------------------------------------------------

@pytest.fixture
def fake_api(monkeypatch):
    """Serve fixtures by amp-api path instead of the network."""
    routes = {}

    def api_get(path, params=None, *, lang=None, label=None):
        for prefix, body in routes.items():
            if path.startswith(prefix):
                return body(params) if callable(body) else body
        raise fetch.AppleMusicNotFound(fetch.not_found_message(path))

    monkeypatch.setattr(fetch, "api_get", api_get)
    for mod in ("songs", "albums", "search", "charts", "shared", "catalog", "browse", "artists", "playlists"):
        module = __import__(f"apple_music.{mod}", fromlist=["x"])
        if hasattr(module, "api_get"):
            monkeypatch.setattr(module, "api_get", api_get)
    return routes


def test_song_details_by_isrc_keeps_exact_matches(fake_api):
    from apple_music import songs
    body = load("isrc")
    body["data"].append({"id": "x", "type": "songs", "attributes": {"isrc": "OTHER0000000", "name": "noise"}})
    fake_api["/v1/catalog/us/songs"] = body
    out = songs.details({"isrc": "USUM71703861"})
    assert out["isrc"] == "USUM71703861"
    assert all(v["isrc"] == "USUM71703861" for v in out["other_versions"])
    assert "noise" not in json.dumps(out)


def test_album_details_by_upc_and_tracks(fake_api):
    from apple_music import albums
    fake_api["/v1/catalog/us/albums"] = load("upc")
    out = albums.details({"upc": "00602547943491"})
    assert out["upc"].lstrip("0") == "602547943491" and out["tracks"]
    assert out["total_duration_ms"] == sum(t["duration_ms"] for t in out["tracks"])
    with pytest.raises(fetch.AppleMusicNotFound):
        albums.details({"upc": "000000000000"})


def test_charts_rank_and_genre_resolution(fake_api):
    from apple_music import charts, shared
    shared._lookups.clear()
    fake_api["/v1/catalog/us/genres"] = load("genres")
    fake_api["/v1/catalog/us/charts"] = load("charts")
    out = charts.top_songs(genre={"id": None, "name": "music"}, limit=3)
    assert out["chart_name"] == "Top Songs" and out["genre"]["id"] == "34"
    assert [s["rank"] for s in out["songs"]] == [1, 2, 3]
    with pytest.raises(ValueError):
        charts.top_songs(genre={"id": None, "name": "bollywood"})


def test_auto_complete(fake_api):
    from apple_music import search
    fake_api["/v1/catalog/us/search/suggestions"] = load("suggestions")
    out = search.auto_complete("drak")
    assert out["suggestions"] and all(isinstance(t, str) for t in out["suggestions"])
    kinds = {kind for kind, _ in P.PARSERS.values()}
    assert out["top_results"] and all(r["type"] in kinds for r in out["top_results"])
