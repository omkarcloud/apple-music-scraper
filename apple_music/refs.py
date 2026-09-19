"""Apple Music reference parsing: ONE param per input that auto-detects its
forms (tripadvisor QueryOrLinkField convention — never a sibling
`url`/`id` pair). Every resolver returns a small JSON-able dict, so the
validated params stay usable as a response-cache key:

  song      1440841367 | USCM51600061 (ISRC)
            | https://music.apple.com/us/song/keep-the-family-close/1440841367
            | https://music.apple.com/us/album/views/1440841363?i=1440841367
            -> {"id": "1440841367", "country": "us"} | {"isrc": "USCM51600061"}
  album     1440841363 | 00602547943491 (UPC/EAN, 12-14 digits)
            | https://music.apple.com/us/album/views/1440841363
            -> {"id": …, "country": …} | {"upc": …}
  artist    271256     | https://music.apple.com/us/artist/drake/271256
  playlist  pl.f4d106fed2bd41149aaacabb233eb5eb
            | https://music.apple.com/us/playlist/todays-hits/pl.f4d1…
  video     1896761455 | https://music.apple.com/us/music-video/high-fives/1896761455
  station   ra.978194965 | https://music.apple.com/us/station/apple-music-1/ra.978194965
  curator   1526756058 | https://music.apple.com/us/curator/apple-music-hits/1526756058
  label     1556733255 | https://music.apple.com/us/label/def-jam/1556733255
  genre     21 | "rock" | https://music.apple.com/us/genre/rock/21 (names resolve per country)

A link's storefront (the `/us/` segment) is kept as `country`; the routes
use it when the caller gives no explicit `country`, so a pasted UK link
just works. classic itunes.apple.com / geo.music.apple.com links resolve
the same way.

Also holds the route tables: search types, artist views, chart types,
browse sections and the Daily Top 100 region aliases.
"""
import re
from urllib.parse import parse_qs, urlparse

_DIGITS_RE = re.compile(r"^\d{1,11}$")
_CODE_RE = re.compile(r"^\d{12,14}$")                        # UPC-A / EAN-13 / GTIN-14
_ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
_PLAYLIST_RE = re.compile(r"^pl\.[A-Za-z0-9-]{6,}$")
_STATION_RE = re.compile(r"^ra\.[A-Za-z0-9.-]{3,}$")
_HOST_RE = re.compile(r"(^|\.)(music|itunes)\.apple\.com$")
_STOREFRONT_RE = re.compile(r"^[a-z]{2}$")
_ID_IN_SEGMENT_RE = re.compile(r"^(?:id)?(\d{1,11})$")


def _parse_link(text, kind):
    """A music.apple.com / itunes.apple.com link -> (path segments, query, storefront).
    Raises ValueError for another site's link."""
    url = text if "://" in text else ("https:" + text if text.startswith("//") else "https://" + text)
    parsed = urlparse(url)
    if not _HOST_RE.search((parsed.hostname or "").lower()):
        raise ValueError(f"{kind} must be an Apple Music id or a music.apple.com link")
    segments = [s for s in parsed.path.split("/") if s]
    storefront = segments[0].lower() if segments and _STOREFRONT_RE.match(segments[0].lower()) else None
    return segments, parse_qs(parsed.query), storefront


def _is_link(text):
    return text.startswith(("http://", "https://", "//")) or "apple.com/" in text


def _link_id(segments, section, pattern, kind):
    """The id that follows `/<section>/<slug>/` (or `/<section>/`) in a link."""
    if section not in segments:
        raise ValueError(f"not an Apple Music {kind} link (expected …/{section}/…)")
    tail = segments[segments.index(section) + 1:]
    for segment in reversed(tail):
        m = pattern.match(segment)
        if m:
            return m.group(1) if m.groups() else segment
    raise ValueError(f"no {kind} id in the link")


def _with_country(ref, storefront):
    ref["country"] = storefront
    return ref


def resolve_song(value):
    text = str(value or "").strip()
    if _DIGITS_RE.match(text):
        return {"id": text, "country": None}
    if _ISRC_RE.match(text.upper().replace("-", "")) and not _is_link(text):
        return {"isrc": text.upper().replace("-", "")}
    if _is_link(text):
        segments, query, storefront = _parse_link(text, "song")
        if query.get("i") and _DIGITS_RE.match(query["i"][0]):
            return _with_country({"id": query["i"][0]}, storefront)
        return _with_country({"id": _link_id(segments, "song", _ID_IN_SEGMENT_RE, "song")}, storefront)
    raise ValueError("song must be an Apple Music song id, an ISRC (e.g. USCM51600061) "
                     "or a music.apple.com song link")


def resolve_album(value):
    text = str(value or "").strip()
    if _DIGITS_RE.match(text):
        return {"id": text, "country": None}
    if _CODE_RE.match(text):
        return {"upc": text}
    if _is_link(text):
        segments, _, storefront = _parse_link(text, "album")
        return _with_country({"id": _link_id(segments, "album", _ID_IN_SEGMENT_RE, "album")}, storefront)
    raise ValueError("album must be an Apple Music album id, a UPC/EAN barcode "
                     "or a music.apple.com album link")


def _simple(kind, section, pattern, example):
    def resolve(value):
        text = str(value or "").strip()
        m = pattern.match(text)
        if m and not _is_link(text):
            return {"id": m.group(1) if m.groups() else text, "country": None}
        if _is_link(text):
            segments, _, storefront = _parse_link(text, kind)
            return _with_country({"id": _link_id(segments, section, pattern, kind)}, storefront)
        raise ValueError(f"{kind} must be an Apple Music {kind} id (e.g. {example}) "
                         f"or a music.apple.com {section} link")
    resolve.__name__ = f"resolve_{kind.replace(' ', '_')}"
    return resolve


resolve_artist = _simple("artist", "artist", _ID_IN_SEGMENT_RE, "271256")
resolve_playlist = _simple("playlist", "playlist", _PLAYLIST_RE, "pl.f4d106fed2bd41149aaacabb233eb5eb")
resolve_music_video = _simple("music video", "music-video", _ID_IN_SEGMENT_RE, "1896761455")
resolve_station = _simple("station", "station", _STATION_RE, "ra.978194965")
resolve_curator = _simple("curator", "curator", _ID_IN_SEGMENT_RE, "1526756058")
resolve_label = _simple("label", "label", _ID_IN_SEGMENT_RE, "1556733255")


def resolve_genre(value):
    """Numeric genre id, a genre link, or a genre NAME (matched per country
    by the route against that storefront's genre list)."""
    text = str(value or "").strip()
    if _DIGITS_RE.match(text):
        return {"id": text, "name": None}
    if _is_link(text):
        segments, _, _ = _parse_link(text, "genre")
        for segment in reversed(segments):
            m = _ID_IN_SEGMENT_RE.match(segment)
            if m:
                return {"id": m.group(1), "name": None}
        raise ValueError("no genre id in the link")
    if len(text) > 60:
        raise ValueError("genre must be a genre id (e.g. 21) or a genre name (e.g. rock)")
    return {"id": None, "name": text}


def resolve_song_list(values):
    """Comma list of song ids / links (no ISRCs: batch is by id)."""
    ids = []
    for value in values or []:
        ref = resolve_song(value)
        if "isrc" in ref:
            raise ValueError(f"{value}: batch takes song ids or links, not ISRCs")
        if ref["id"] not in ids:
            ids.append(ref["id"])
    return ids


# ---- route tables -------------------------------------------------------------

# public search type -> amp-api `types` token(s)
SEARCH_TYPES = {
    "songs": ["songs"],
    "albums": ["albums"],
    "artists": ["artists"],
    "playlists": ["playlists"],
    "music-videos": ["music-videos"],
    "stations": ["stations"],
    "curators": ["apple-curators", "curators"],
    "labels": ["record-labels"],
}
# search/all fans out to two calls: amp-api drops the rarer types when they
# ride along with the four core ones (verified 2026-09-19).
SEARCH_ALL_CORE = ["songs", "albums", "artists", "playlists"]
SEARCH_ALL_EXTRA = ["music-videos", "stations", "apple-curators", "curators", "record-labels"]
SUGGESTION_TYPES = "songs,albums,artists,playlists,music-videos,stations"

# public artist album type -> artist view (None = the full `albums` relationship)
ARTIST_ALBUM_TYPES = {
    "all": None,
    "albums": "full-albums",
    "singles": "singles",
    "live": "live-albums",
    "compilations": "compilation-albums",
    "appears-on": "appears-on-albums",
    "essential": "featured-albums",
}
ARTIST_PLAYLIST_TYPES = {"artist": "playlists", "featured": "featured-playlists"}
ARTIST_VIDEO_TYPES = {"all": "music-videos", "top": "top-music-videos"}

# every artist view the artist page asks for (details overview)
ARTIST_DETAIL_VIEWS = [
    "latest-release", "top-songs", "featured-albums", "full-albums", "singles", "live-albums",
    "compilation-albums", "appears-on-albums", "top-music-videos", "music-videos",
    "playlists", "featured-playlists", "similar-artists", "radio-shows", "more-to-hear",
    "more-to-see",
]
ALBUM_RELATED_VIEWS = ["other-versions", "more-by-artist", "you-might-also-like",
                       "appears-on", "related-videos", "audio-extras"]

CHART_TYPES = {"songs": "songs", "albums": "albums", "playlists": "playlists",
               "music-videos": "music-videos"}

# Browse page shortcuts: public name -> the section's English title on the
# editorial "music" grouping (looked up in en-US, served in the caller's lang).
BROWSE_SECTIONS = {
    "new-releases": "New This Week",
    "recent-releases": "Recent Releases",
    "best-new-songs": "Best New Songs",
    "trending-songs": "Trending Songs",
    "coming-soon": "Coming Soon",
    "updated-playlists": "Updated Playlists",
    "popular": "Everyone’s Listening To...",
    "dj-mixes": "DJ Mixes of the Month",
}
ROOM_SORTS = {"featured": "featured", "release-date": "releaseDate", "name": "alphabet"}

# Daily Top 100 playlists are titled "Top 100: <region>"; these regions do
# not match the storefront's English name.
TOP_100_REGION_ALIASES = {
    "usa": "us", "uk": "gb", "south korea": "kr", "russia": "ru", "czechia": "cz",
    "micronesia": "fm", "vietnam": "vn", "laos": "la", "moldova": "md", "tanzania": "tz",
    "bolivia": "bo", "venezuela": "ve", "taiwan": "tw", "hong kong": "hk", "macau": "mo",
    "türkiye": "tr", "turkey": "tr", "uae": "ae", "united arab emirates": "ae",
    "côte d’ivoire": "ci", "cote d'ivoire": "ci", "ivory coast": "ci",
}
