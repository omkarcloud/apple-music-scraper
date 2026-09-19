"""/apple-music/browse*, /apple-music/radio — Apple Music's editorial pages
(the Browse tab and the Radio tab) and their "see all" sections."""
from apple_music import parsers as P
from apple_music import refs
from apple_music.fetch import AppleMusicNotFound, api_get, run_parallel
from apple_music.shared import browse_room_ids, grouping, paged, storefront

ROOM_MAX = 100


def browse(country=None, lang=None):
    """The Browse page: every shelf (featured banners, Best New Songs, New This
    Week, Recent Releases, Updated Playlists, Trending Songs, Daily Top 100,
    City Charts, live radio, Coming Soon, …) with its items and the
    `see_all_id` to page through it with /apple-music/browse/section."""
    sf = storefront(country)
    sections, links = P.grouping_sections(grouping(sf, lang=lang, name="music"))
    return {"country": sf.upper(), "sections": sections, "explore_links": links}


def radio(country=None, lang=None):
    """The Radio page: live stations on air now, radio shows, episodes,
    interviews, hosts and broadcasters."""
    sf = storefront(country)
    sections, links = P.grouping_sections(grouping(sf, lang=lang, name="radio"))
    return {"country": sf.upper(), "sections": sections, "explore_links": links}


def section(section, sort=None, page=1, limit=50, country=None, lang=None):
    """Every item of one editorial section ("see all" room), paged and
    optionally sorted (featured, release-date, name)."""
    sf = storefront(country)
    path = f"/v1/editorial/{sf}/rooms/{section}"

    def info():
        body = api_get(path, None, lang=lang)
        data = (body or {}).get("data") or []
        if not data:
            raise AppleMusicNotFound(f"section {section} not found")
        return P.room_info(data[0])

    def contents():
        return paged(path + "/contents", page, limit, max_per_call=ROOM_MAX, lang=lang,
                     params={"sort": refs.ROOM_SORTS.get(sort) if sort else None}, typed=True)

    head, (items, pagination) = run_parallel([info, contents])
    return {"section": head, "sort": sort or head.get("default_sort"), "items": items, "pagination": pagination}


def _shortcut(name):
    title = refs.BROWSE_SECTIONS[name]

    def handler(sort=None, page=1, limit=50, country=None, lang=None):
        sf = storefront(country)
        room_id = browse_room_ids(sf).get(title)
        if not room_id:
            raise AppleMusicNotFound(f"the Browse page in {sf.upper()} has no {title!r} section")
        return section(room_id, sort=sort, page=page, limit=limit, country=sf, lang=lang)

    handler.__name__ = name.replace("-", "_")
    handler.__doc__ = f"The Browse page's {title!r} section, paged."
    return handler


new_releases = _shortcut("new-releases")
recent_releases = _shortcut("recent-releases")
best_new_songs = _shortcut("best-new-songs")
trending_songs = _shortcut("trending-songs")
coming_soon = _shortcut("coming-soon")
updated_playlists = _shortcut("updated-playlists")
popular = _shortcut("popular")
dj_mixes = _shortcut("dj-mixes")
