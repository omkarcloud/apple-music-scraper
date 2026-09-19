"""Helpers shared by the Apple Music endpoint modules: storefront choice,
paged collections and the in-process lookup tables (genres, editorial
sections, chart playlists) that several routes resolve names against."""
import threading
import time

from apple_music import parsers as P
from apple_music.fetch import AppleMusicNotFound, api_get, catalog_get, page_range

DEFAULT_COUNTRY = "us"
LOOKUP_TTL = 3600          # seconds an in-process lookup table is reused


def storefront(country=None, ref=None):
    """Explicit `country` wins, then a pasted link's storefront, then us."""
    return (country or (ref or {}).get("country") or DEFAULT_COUNTRY).lower()


def offset_of(page, limit):
    return (page - 1) * limit


def paged(path, page, limit, *, max_per_call, lang=None, params=None, key=None, typed=False,
          numbered=None):
    """One page of a paged amp-api collection -> (parsed items, pagination).
    numbered="rank"/"position" stamps each item with its 1-based place."""
    offset = offset_of(page, limit)
    raw, has_more = page_range(path, offset, limit, max_per_call=max_per_call, lang=lang,
                               params=params, key=key)
    parsed = P.items(raw, typed=typed)
    if numbered:
        parsed = [{numbered: offset + i + 1, **x} for i, x in enumerate(parsed)]
    return parsed, P.pagination(page, limit, has_more)


def numbered_items(objs, field, start=0, typed=False):
    return [{field: start + i + 1, **x} for i, x in enumerate(P.items(objs, typed=typed))]


# ---- in-process lookup tables ----------------------------------------------------

_lookup_lock = threading.Lock()
_lookups = {}


def lookup(key, build):
    """Memoise build() for LOOKUP_TTL seconds (genre lists, section ids…)."""
    now = time.time()
    with _lookup_lock:
        hit = _lookups.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = build()
    with _lookup_lock:
        _lookups[key] = (now + LOOKUP_TTL, value)
    return value


def genre_list(country):
    return lookup(("genres", country), lambda: catalog_get(country, "genres", {"l": "en-US"}).get("data") or [])


def resolve_genre(ref, country):
    """{"id"} | {"name"} -> (genre id, genre name) valid in `country`.
    Names match the storefront's genre list case-insensitively (en-US)."""
    if not ref:
        return None, None
    genres = genre_list(country)
    if ref.get("id"):
        for g in genres:
            if g.get("id") == ref["id"]:
                return g["id"], (g.get("attributes") or {}).get("name")
        return ref["id"], None          # sub-genre ids still work for some calls; upstream validates
    wanted = ref["name"].strip().lower().replace("&", "and")
    for g in genres:
        name = ((g.get("attributes") or {}).get("name") or "")
        if name.lower().replace("&", "and") == wanted:
            return g["id"], name
    for g in genres:
        name = ((g.get("attributes") or {}).get("name") or "")
        if wanted in name.lower().replace("&", "and"):
            return g["id"], name
    names = ", ".join((g.get("attributes") or {}).get("name") or "" for g in genres if g.get("id") != "34")
    raise ValueError(f"unknown genre {ref['name']!r} in country {country.upper()}; one of: {names}")


def grouping(country, lang=None, **params):
    return api_get(f"/v1/editorial/{country}/groupings", {"platform": "web", **params}, lang=lang)


def browse_room_ids(country):
    """English section title -> room id on the Browse page of `country`."""
    def build():
        body = grouping(country, lang="en-US", name="music")
        sections, _ = P.grouping_sections(body)
        return {s["title"]: s["see_all_id"] for s in sections if s.get("see_all_id")}
    return lookup(("browse-rooms", country), build)


def require(value, message):
    if not value:
        raise AppleMusicNotFound(message)
    return value
