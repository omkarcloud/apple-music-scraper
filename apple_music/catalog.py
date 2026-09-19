"""/apple-music/{genres,countries,labels,curators,stations}/* — the smaller
catalog resources."""
from apple_music import parsers as P
from apple_music.fetch import AppleMusicNotFound, api_get, catalog_get, resource
from apple_music.shared import genre_list, grouping, paged, resolve_genre, storefront

CURATOR_PAGE_MAX = {"apple-curators": 25, "curators": 10}   # amp-api caps per call
LABEL_VIEW_MAX = 100


# ---- countries / genres -------------------------------------------------------------

def countries(lang=None):
    """Every Apple Music storefront (country) with its languages."""
    body = api_get("/v1/storefronts", {"limit": 200}, lang=lang or "en-US")
    rows = sorted(P.items(body.get("data")), key=lambda c: c.get("name") or "")
    return {"count": len(rows), "countries": rows}


def genres(country=None, lang=None):
    """The top-level genres of one country's catalog (they differ per country:
    India has Bollywood, Tamil, Telugu…). Use an id or a name as `genre`
    on the chart endpoints."""
    sf = storefront(country)
    data = genre_list(sf) if not lang else (catalog_get(sf, "genres", None, lang=lang).get("data") or [])
    return {"country": sf.upper(), "genres": P.items(data)}


def genre_details(genre, country=None, lang=None):
    """A genre's page: its editorial shelves (featured playlists, essentials,
    artist playlists…) in `country`."""
    sf = storefront(country)
    genre_id, name = resolve_genre(genre, sf)
    body = grouping(sf, lang=lang, genre=genre_id)
    sections, links = P.grouping_sections(body)
    return {"genre": {"id": genre_id, "name": name}, "country": sf.upper(),
            "sections": sections, "explore_links": links}


# ---- labels -----------------------------------------------------------------------------

def label_details(label, country=None, lang=None):
    """A record label: description, artwork and the first latest/top releases."""
    sf = storefront(country, label)
    obj = resource(sf, "record-labels", label["id"], {"views": "latest-releases,top-releases"}, lang=lang)
    out = P.label(obj)
    out.update({
        "latest_releases": P.items(P.view(obj, "latest-releases")),
        "latest_releases_has_more": P.view_has_more(obj, "latest-releases"),
        "top_releases": P.items(P.view(obj, "top-releases")),
        "top_releases_has_more": P.view_has_more(obj, "top-releases"),
    })
    return out


def label_releases(label, type="latest", page=1, limit=20, country=None, lang=None):
    """A label's releases: latest (newest first) or top (most popular)."""
    sf = storefront(country, label)
    items, pagination = paged(f"/v1/catalog/{sf}/record-labels/{label['id']}/view/{type}-releases",
                              page, limit, max_per_call=LABEL_VIEW_MAX, lang=lang)
    return {"label_id": label["id"], "type": type, "albums": items, "pagination": pagination}


# ---- curators ---------------------------------------------------------------------------

def _curator(sf, cid, lang, params):
    """Apple curators (Apple Music Hits, radio shows) and external curators
    share the /curator/ link shape but live under different resource types."""
    try:
        return resource(sf, "apple-curators", cid, {"platform": "web", **params}, lang=lang)
    except AppleMusicNotFound:
        # external curators have no page grouping: ask only for playlists
        external = {"include": "playlists"} if params.get("include") else {}
        return resource(sf, "curators", cid, external, lang=lang)


def curator_details(curator, country=None, lang=None):
    """A curator (Apple Music editorial brand, radio show or external
    curator): description, host, playlists and — for Apple curators — the
    curator page's shelves (episodes, interviews, playlists…)."""
    sf = storefront(country, curator)
    obj = _curator(sf, curator["id"], lang, {"include": "grouping,playlists"})
    groupings = [g for g in ((obj.get("relationships") or {}).get("grouping") or {}).get("data") or []]
    sections = P.grouping_sections({"data": groupings[:1]})[0] if groupings else []
    playlists_block = (obj.get("relationships") or {}).get("playlists") or {}
    out = P.curator(obj)
    out.update({
        "playlists": P.items(playlists_block.get("data")),
        "playlists_has_more": bool(playlists_block.get("next")),
        "sections": sections,
    })
    return out


def curator_playlists(curator, page=1, limit=25, country=None, lang=None):
    """Every playlist a curator publishes, paged."""
    sf = storefront(country, curator)
    for kind in ("apple-curators", "curators"):
        try:
            items, pagination = paged(f"/v1/catalog/{sf}/{kind}/{curator['id']}/playlists", page, limit,
                                      max_per_call=CURATOR_PAGE_MAX[kind], lang=lang)
        except AppleMusicNotFound:
            continue
        # a 404 (wrong curator type) is swallowed as an empty page, so an
        # empty page must fall through to the other type even past page 1
        if items:
            return {"curator_id": curator["id"], "playlists": items, "pagination": pagination}
    # page_range swallows a 404 as "empty", so an unknown id lands here
    _curator(sf, curator["id"], lang, {})   # raises NotFound for an unknown id
    return {"curator_id": curator["id"], "playlists": [], "pagination": P.pagination(page, limit, False)}


# ---- stations ---------------------------------------------------------------------------

def live_stations(country=None, lang=None):
    """Apple Music's live radio stations (Apple Music 1, Hits, Country,
    Música Uno, Club, Chill…)."""
    sf = storefront(country)
    body = catalog_get(sf, "stations", {"filter[featured]": "apple-music-live-radio"}, lang=lang)
    return {"country": sf.upper(), "stations": P.items((body or {}).get("data"))}


def station_details(station, country=None, lang=None):
    """One station: live station, artist station, radio show episode or
    local broadcaster."""
    sf = storefront(country, station)
    return P.station(resource(sf, "stations", station["id"], {"extend": "editorialVideo"}, lang=lang))
