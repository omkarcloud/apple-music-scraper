"""/apple-music/songs/* — song details (by id, ISRC or link) and batch."""
from apple_music import parsers as P
from apple_music.fetch import AppleMusicNotFound, catalog_get
from apple_music.shared import storefront

SONG_INCLUDE = "albums,artists,composers,genres,music-videos,station"
SONG_EXTEND = "editorialNotes,editorialArtwork"
BATCH_MAX = 100


def song_detail(obj, other_versions=None):
    """A song with its relationships resolved."""
    out = P.song(obj)
    albums = P.rel(obj, "albums")
    genres = P.rel(obj, "genres")
    stations = P.rel(obj, "station")
    out.update({
        "album": P.album(albums[0]) if albums else None,
        "artists": P.items(P.rel(obj, "artists")),
        "composers": P.items(P.rel(obj, "composers")),
        "primary_genre": P.genre(genres[0]) if genres else None,
        "music_videos": P.items(P.rel(obj, "music-videos")),
        "radio_station": P.station(stations[0]) if stations else None,
        "other_versions": other_versions if other_versions is not None else [],
    })
    return out


def details(song, country=None, lang=None):
    """Full song details. `song` is an id, an ISRC or a music.apple.com link;
    an ISRC can map to several catalog songs (single, album, deluxe…): the
    first is detailed and the rest listed under other_versions."""
    sf = storefront(country, song)
    params = {"include": SONG_INCLUDE, "extend": SONG_EXTEND}
    if song.get("isrc"):
        body = catalog_get(sf, "songs", {**params, "filter[isrc]": song["isrc"]}, lang=lang)
        # amp-api's filter is loose on malformed codes: keep exact matches only
        data = [d for d in (body or {}).get("data") or []
                if ((d.get("attributes") or {}).get("isrc") or "").upper() == song["isrc"]]
        if not data:
            raise AppleMusicNotFound(f"no song with ISRC {song['isrc']} in the {sf.upper()} catalog")
        return song_detail(data[0], other_versions=P.items(data[1:]))
    body = catalog_get(sf, f"songs/{song['id']}", params, lang=lang)
    data = (body or {}).get("data") or []
    if not data:
        raise AppleMusicNotFound(f"song {song['id']} not found in the {sf.upper()} catalog")
    return song_detail(data[0])


def batch(songs, country=None, lang=None):
    """Up to 100 songs by id in one call; unknown ids are listed in not_found."""
    if len(songs) > BATCH_MAX:
        raise ValueError(f"at most {BATCH_MAX} songs per batch")
    sf = storefront(country)
    body = catalog_get(sf, "songs", {"ids": ",".join(songs)}, lang=lang)
    found = P.items((body or {}).get("data"))
    by_id = {s["id"]: s for s in found}
    return {
        "songs": [by_id[i] for i in songs if i in by_id],
        "not_found": [i for i in songs if i not in by_id],
    }
