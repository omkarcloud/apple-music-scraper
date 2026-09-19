"""/apple-music/artists/* — the artist page overview and each paged shelf."""
from apple_music import parsers as P
from apple_music import refs
from apple_music.fetch import resource
from apple_music.shared import paged, storefront

ARTIST_EXTEND = "artistBio,editorialArtwork,editorialVideo,plainEditorialNotes"
VIEW_MAX = 100          # amp-api caps artist views and the albums relationship at 100 per call


def details(artist, country=None, lang=None):
    """The whole artist page: bio, origin, born/formed, artwork, radio
    station, latest release and the first items of every shelf (top songs,
    albums, singles, live, compilations, appears on, music videos, playlists,
    similar artists, radio shows, more to hear/see). Each shelf's `*_has_more`
    says whether the matching paged endpoint has more."""
    sf = storefront(country, artist)
    obj = resource(sf, "artists", artist["id"], {
        "views": ",".join(refs.ARTIST_DETAIL_VIEWS), "extend": ARTIST_EXTEND,
        "include": "genres,station",
    }, lang=lang)
    out = P.artist(obj)
    genres = P.rel(obj, "genres")
    stations = P.rel(obj, "station")
    latest = P.view(obj, "latest-release")
    out.update({
        "primary_genre": P.genre(genres[0]) if genres else None,
        "radio_station": P.station(stations[0]) if stations else None,
        "latest_release": P.album(latest[0]) if latest else None,
    })
    shelves = [
        ("top_songs", "top-songs", False), ("essential_albums", "featured-albums", False),
        ("albums", "full-albums", False), ("singles_and_eps", "singles", False),
        ("live_albums", "live-albums", False), ("compilations", "compilation-albums", False),
        ("appears_on", "appears-on-albums", False), ("top_music_videos", "top-music-videos", False),
        ("music_videos", "music-videos", False), ("artist_playlists", "playlists", False),
        ("featured_playlists", "featured-playlists", False), ("similar_artists", "similar-artists", False),
        ("radio_shows", "radio-shows", False), ("more_to_hear", "more-to-hear", True),
        ("more_to_see", "more-to-see", True),
    ]
    for key, view_name, typed in shelves:
        out[key] = P.items(P.view(obj, view_name), typed=typed)
        out[f"{key}_has_more"] = P.view_has_more(obj, view_name)
    return out


def _artist_list(artist, country, view_path, page, limit, lang, out_key, typed=False, numbered=None):
    sf = storefront(country, artist)
    items, pagination = paged(f"/v1/catalog/{sf}/artists/{artist['id']}/{view_path}", page, limit,
                              max_per_call=VIEW_MAX, lang=lang, typed=typed, numbered=numbered)
    return {"artist_id": artist["id"], out_key: items, "pagination": pagination}


def top_songs(artist, page=1, limit=20, country=None, lang=None):
    """The artist's most-played songs, ranked."""
    return _artist_list(artist, country, "view/top-songs", page, limit, lang, "songs", numbered="rank")


def albums(artist, type="all", page=1, limit=20, country=None, lang=None):
    """Albums by type: all (the full discography, every kind), albums
    (studio LPs), singles (singles & EPs), live, compilations, appears-on,
    essential."""
    view_name = refs.ARTIST_ALBUM_TYPES[type]
    path = "albums" if view_name is None else f"view/{view_name}"
    result = _artist_list(artist, country, path, page, limit, lang, "albums")
    result["type"] = type
    return result


def music_videos(artist, type="all", page=1, limit=20, country=None, lang=None):
    """Music videos: all (newest first) or top (most watched)."""
    result = _artist_list(artist, country, f"view/{refs.ARTIST_VIDEO_TYPES[type]}", page, limit, lang,
                          "music_videos")
    result["type"] = type
    return result


def playlists(artist, type="artist", page=1, limit=20, country=None, lang=None):
    """Playlists: artist (Essentials, Next Steps, Influences, Inspired By, Set
    List…) or featured (editorial playlists that feature the artist)."""
    result = _artist_list(artist, country, f"view/{refs.ARTIST_PLAYLIST_TYPES[type]}", page, limit, lang,
                          "playlists")
    result["type"] = type
    return result


def similar(artist, page=1, limit=20, country=None, lang=None):
    """Artists Apple Music lists as similar."""
    return _artist_list(artist, country, "view/similar-artists", page, limit, lang, "artists")
