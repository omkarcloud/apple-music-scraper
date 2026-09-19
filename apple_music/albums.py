"""/apple-music/albums/* — album details with the full tracklist, and the
album page's related shelves."""
from apple_music import parsers as P
from apple_music.fetch import AppleMusicNotFound, catalog_get, follow_all
from apple_music.shared import storefront

ALBUM_INCLUDE = "tracks,artists,record-labels,genres"
ALBUM_EXTEND = "editorialVideo,editorialArtwork,plainEditorialNotes"
MAX_TRACKS = 500


def _fetch(album, sf, lang, params):
    if album.get("upc"):
        body = catalog_get(sf, "albums", {**params, "filter[upc]": album["upc"]}, lang=lang)
        # amp-api's filter is loose (an all-zero code matches real albums):
        # keep albums whose barcode equals the request, ignoring leading zeros
        wanted = album["upc"].lstrip("0")
        data = [d for d in (body or {}).get("data") or []
                if ((d.get("attributes") or {}).get("upc") or "").lstrip("0") == wanted and wanted]
        if not data:
            raise AppleMusicNotFound(f"no album with UPC {album['upc']} in the {sf.upper()} catalog")
        return data[0], data[1:]
    body = catalog_get(sf, f"albums/{album['id']}", params, lang=lang)
    data = (body or {}).get("data") or []
    if not data:
        raise AppleMusicNotFound(f"album {album['id']} not found in the {sf.upper()} catalog")
    return data[0], []


def details(album, country=None, lang=None):
    """Full album: metadata, editorial notes, label, artists and every track
    (songs and music videos, numbered by disc/track). `album` is an id, a
    UPC/EAN or a music.apple.com link; a UPC can match several editions
    (explicit/clean): the first is detailed, the rest listed."""
    sf = storefront(country, album)
    obj, others = _fetch(album, sf, lang, {"include": ALBUM_INCLUDE, "extend": ALBUM_EXTEND})
    tracks_block = ((obj.get("relationships") or {}).get("tracks") or {})
    tracks = follow_all(tracks_block, max_items=MAX_TRACKS, lang=lang)
    track_items = P.items(tracks, typed=True)
    total_ms = sum(t.get("duration_ms") or 0 for t in track_items) or None
    genres = P.rel(obj, "genres")
    out = P.album(obj)
    out.update({
        "total_duration_ms": total_ms,
        "total_duration": P.duration_text(total_ms),
        "primary_genre": P.genre(genres[0]) if genres else None,
        "artists": P.items(P.rel(obj, "artists")),
        "labels": P.items(P.rel(obj, "record-labels")),
        "tracks": track_items,
        "other_versions": P.items(others),
    })
    return out


def related(album, country=None, lang=None):
    """The album page's shelves: other versions, more by the artist, you might
    also like, playlists featuring it, its music videos and audio extras."""
    sf = storefront(country, album)
    obj, _ = _fetch(album, sf, lang, {"views": ",".join([
        "other-versions", "more-by-artist", "you-might-also-like", "appears-on",
        "related-videos", "audio-extras"])})
    return {
        "album": {"id": obj.get("id"), "name": (obj.get("attributes") or {}).get("name"),
                  "link": (obj.get("attributes") or {}).get("url")},
        "other_versions": P.items(P.view(obj, "other-versions")),
        "more_by_artist": P.items(P.view(obj, "more-by-artist")),
        "you_might_also_like": P.items(P.view(obj, "you-might-also-like")),
        "featured_in_playlists": P.items(P.view(obj, "appears-on"), typed=True),
        "music_videos": P.items(P.view(obj, "related-videos"), typed=True),
        "audio_extras": P.items(P.view(obj, "audio-extras"), typed=True),
    }
