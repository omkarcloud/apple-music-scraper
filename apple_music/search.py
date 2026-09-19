"""/apple-music/search/* — autocomplete, all-types search and one paged
search per resource type."""
from apple_music import parsers as P
from apple_music import refs
from apple_music.fetch import catalog_get, run_parallel
from apple_music.shared import offset_of, storefront


def auto_complete(query, country=None, lang=None):
    """Search-box suggestions: completed terms plus the top matching items."""
    sf = storefront(country)
    body = catalog_get(sf, "search/suggestions", {
        "term": query, "kinds": "terms,topResults", "types": refs.SUGGESTION_TYPES, "limit": 10,
    }, lang=lang)
    suggestions = ((body or {}).get("results") or {}).get("suggestions") or []
    terms = [s.get("displayTerm") or s.get("searchTerm") for s in suggestions
             if s.get("kind") == "terms" and (s.get("displayTerm") or s.get("searchTerm"))]
    top = [s.get("content") for s in suggestions if s.get("kind") == "topResults" and s.get("content")]
    return {"query": query, "suggestions": terms, "top_results": P.items(top, typed=True)}


def _block(body, kind):
    return (((body or {}).get("results") or {}).get(kind) or {})


def search_all(query, limit=5, country=None, lang=None):
    """Every result type at once: top results + the first `limit` of each."""
    sf = storefront(country)

    def core():
        return catalog_get(sf, "search", {"term": query, "types": ",".join(refs.SEARCH_ALL_CORE),
                                          "limit": limit, "with": "topResults"}, lang=lang)

    def extra():
        return catalog_get(sf, "search", {"term": query, "types": ",".join(refs.SEARCH_ALL_EXTRA),
                                          "limit": limit}, lang=lang)

    main, more = run_parallel([core, extra])
    curators = _block(more, "apple-curators").get("data", []) + _block(more, "curators").get("data", [])
    return {
        "query": query,
        "top_results": P.items(_block(main, "topResults").get("data"), typed=True),
        "songs": P.items(_block(main, "songs").get("data")),
        "albums": P.items(_block(main, "albums").get("data")),
        "artists": P.items(_block(main, "artists").get("data")),
        "playlists": P.items(_block(main, "playlists").get("data")),
        "music_videos": P.items(_block(more, "music-videos").get("data")),
        "stations": P.items(_block(more, "stations").get("data")),
        "curators": P.items(curators[:limit]),
        "labels": P.items(_block(more, "record-labels").get("data")),
    }


def _typed_search(kind):
    types = refs.SEARCH_TYPES[kind]
    out_key = kind.replace("-", "_")

    def search(query, page=1, limit=25, country=None, lang=None):
        sf = storefront(country)
        body = catalog_get(sf, "search", {"term": query, "types": ",".join(types), "limit": limit,
                                          "offset": offset_of(page, limit) or None}, lang=lang)
        data, has_more = [], False
        for t in types:
            block = _block(body, t)
            data.extend(block.get("data") or [])
            has_more = has_more or bool(block.get("next"))
        return {"query": query, out_key: P.items(data),
                "pagination": P.pagination(page, limit, has_more)}

    search.__name__ = f"search_{out_key}"
    search.__doc__ = f"Paged {kind} search."
    return search


search_songs = _typed_search("songs")
search_albums = _typed_search("albums")
search_artists = _typed_search("artists")
search_playlists = _typed_search("playlists")
search_music_videos = _typed_search("music-videos")
search_stations = _typed_search("stations")
search_curators = _typed_search("curators")
search_labels = _typed_search("labels")
