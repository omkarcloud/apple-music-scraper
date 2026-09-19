"""/apple-music/playlists/* — playlist details and paged tracks."""
from apple_music import parsers as P
from apple_music.fetch import resource
from apple_music.shared import numbered_items, paged, storefront

PLAYLIST_EXTEND = "editorialVideo,editorialArtwork,plainEditorialNotes"
TRACKS_MAX = 100


def details(playlist, country=None, lang=None):
    """Playlist metadata, curator, the first 100 tracks (numbered by
    position), featured artists and more playlists by the same curator.
    Page through longer playlists with /apple-music/playlists/tracks."""
    sf = storefront(country, playlist)
    obj = resource(sf, "playlists", playlist["id"], {
        "include": "tracks,curator", "extend": PLAYLIST_EXTEND,
        "views": "featured-artists,more-by-curator",
    }, lang=lang)
    curators = P.rel(obj, "curator")
    tracks_block = (obj.get("relationships") or {}).get("tracks") or {}
    out = P.playlist(obj)
    out.update({
        "curator": P.curator(curators[0]) if curators else None,
        "tracks": numbered_items(tracks_block.get("data"), "position", typed=True),
        "tracks_has_more": bool(tracks_block.get("next")),
        "featured_artists": P.items(P.view(obj, "featured-artists")),
        "more_by_curator": P.items(P.view(obj, "more-by-curator")),
    })
    return out


def tracks(playlist, page=1, limit=100, country=None, lang=None):
    """One page of a playlist's tracks, numbered by position."""
    sf = storefront(country, playlist)
    items, pagination = paged(f"/v1/catalog/{sf}/playlists/{playlist['id']}/tracks", page, limit,
                              max_per_call=TRACKS_MAX, lang=lang, typed=True, numbered="position")
    return {"playlist_id": playlist["id"], "tracks": items, "pagination": pagination}
