"""/apple-music/charts/* — Apple Music's most-played charts per country and
genre, the Daily Top 100 chart playlists (global + ~115 countries) and the
City Top 25 chart playlists (~106 cities)."""
import re
import unicodedata

from apple_music import parsers as P
from apple_music.fetch import AppleMusicNotFound, api_get, catalog_get, resource
from apple_music.shared import lookup, numbered_items, paged, resolve_genre, storefront

CHART_MAX = 100
DAILY_TOP_CHART_ID = "119"     # `with=dailyGlobalTopCharts` pages by chartId=119
CITY_CHART_ID = "135"          # `with=cityCharts` pages by chartId=135
_TOP_PREFIX_RE = re.compile(r"^Top\s+\d+\s*:\s*", re.I)


def _chart(kind, genre, page, limit, country, lang):
    sf = storefront(country)
    genre_id, genre_name = resolve_genre(genre, sf)
    chart_name = {}

    def pick(body):
        block = ((((body or {}).get("results") or {}).get(kind)) or [{}])[0]
        chart_name.setdefault("name", block.get("name"))
        return block

    items, pagination = paged(f"/v1/catalog/{sf}/charts", page, limit, max_per_call=CHART_MAX, lang=lang,
                              params={"types": kind, "chart": "most-played", "genre": genre_id},
                              key=pick, numbered="rank")
    return {
        "chart_name": chart_name.get("name"),
        "country": sf.upper(),
        "genre": {"id": genre_id, "name": genre_name} if genre_id else None,
        kind.replace("-", "_"): items,
        "pagination": pagination,
    }


def top_songs(genre=None, page=1, limit=50, country=None, lang=None):
    """Top Songs chart (most played), optionally for one genre."""
    return _chart("songs", genre, page, limit, country, lang)


def top_albums(genre=None, page=1, limit=50, country=None, lang=None):
    """Top Albums chart, optionally for one genre."""
    return _chart("albums", genre, page, limit, country, lang)


def top_playlists(genre=None, page=1, limit=50, country=None, lang=None):
    """Top Playlists chart, optionally for one genre."""
    return _chart("playlists", genre, page, limit, country, lang)


def top_music_videos(genre=None, page=1, limit=50, country=None, lang=None):
    """Top Music Videos chart, optionally for one genre."""
    return _chart("music-videos", genre, page, limit, country, lang)


# ---- chart playlists ------------------------------------------------------------

def _fold(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _country_codes():
    """English storefront name (folded) -> ISO code, plus the chart aliases."""
    def build():
        body = api_get("/v1/storefronts", {"limit": 200}, lang="en-US")
        names = {_fold((s.get("attributes") or {}).get("name")): s.get("id") for s in body.get("data") or []}
        from apple_music.refs import TOP_100_REGION_ALIASES
        names.update({_fold(k): v for k, v in TOP_100_REGION_ALIASES.items()})
        return names
    return lookup(("storefront-names",), build)


def _chart_playlists(chart_id, block_key):
    def build():
        body = catalog_get("us", "charts", {"chartId": chart_id, "limit": 200}, lang="en-US")
        return ((((body or {}).get("results") or {}).get(block_key)) or [{}])[0].get("data") or []
    return lookup(("chart-playlists", chart_id), build)


def _top_100_entries():
    codes = _country_codes()
    out = []
    for obj in _chart_playlists(DAILY_TOP_CHART_ID, "dailyGlobalTopCharts"):
        region = _TOP_PREFIX_RE.sub("", (obj.get("attributes") or {}).get("name") or "").strip()
        code = "global" if _fold(region) == "global" else codes.get(_fold(region))
        out.append((region, code, obj))
    return out


def daily_top_100_list(lang=None):
    """Every Daily Top 100 chart playlist: Global plus one per country."""
    entries = _top_100_entries()
    return {"charts": [{"region": region, "country_code": code.upper() if code and code != "global" else code,
                        **P.playlist(obj)} for region, code, obj in entries]}


def daily_top_100(region="global", lang=None):
    """Today's Top 100 songs for `region` (global or an ISO country code),
    ranked, from Apple Music's Daily Top 100 chart playlist."""
    region = region.lower()
    match = next(((r, obj) for r, code, obj in _top_100_entries() if code == region), None)
    if not match:
        raise AppleMusicNotFound(f"Apple Music has no Daily Top 100 chart for {region.upper()}; "
                                 "see /apple-music/charts/daily-top-100-list")
    name, obj = match
    return _chart_playlist(obj["id"], "us" if region == "global" else region, lang,
                           {"region": name, "country_code": region.upper() if region != "global" else "global"})


def _chart_playlist(playlist_id, sf, lang, head):
    try:
        pl = resource(sf, "playlists", playlist_id, {"include": "tracks"}, lang=lang)
    except AppleMusicNotFound:
        pl = resource("us", "playlists", playlist_id, {"include": "tracks"}, lang=lang)
    tracks = ((pl.get("relationships") or {}).get("tracks") or {}).get("data")
    return {**head, "playlist": P.playlist(pl), "songs": numbered_items(tracks, "rank")}


def _city_entries():
    return [(_TOP_PREFIX_RE.sub("", (o.get("attributes") or {}).get("name") or "").strip(), o)
            for o in _chart_playlists(CITY_CHART_ID, "cityCharts")]


def city_charts_list(lang=None):
    """Every City Top 25 chart playlist (~106 cities worldwide)."""
    return {"charts": [{"city": city, **P.playlist(obj)} for city, obj in _city_entries()]}


def city_top_25(city, lang=None):
    """Today's Top 25 songs in one city. `city` is a city name ("Mumbai",
    "new york city") or the chart playlist id."""
    wanted = _fold(city)
    entries = _city_entries()
    match = (next(((c, o) for c, o in entries if o.get("id") == city), None)
             or next(((c, o) for c, o in entries if _fold(c) == wanted), None)
             or next(((c, o) for c, o in entries if wanted and wanted in _fold(c)), None))
    if not match:
        raise AppleMusicNotFound(f"no City Top 25 chart for {city!r}; see /apple-music/charts/city-charts-list")
    name, obj = match
    return _chart_playlist(obj["id"], "us", lang, {"city": name})
