"""The 51 Apple Music endpoints. Every path is served with and without the
`/apple-music` prefix, so code generated against the hosted API on RapidAPI
(paths like /songs/details) runs unchanged against this server.

Params are validated by the marshmallow schemas in apple_music/schemas.py
(the same ones the hosted API uses): ONE param per input — `song` takes an
id, an ISRC or a music.apple.com link, `album` an id, a UPC or a link, and
so on. Unknown params are rejected with a 400 so typos surface."""
import json
from urllib.parse import urlencode

from bottle import request, response, route

from apple_music import albums, artists, browse, catalog, charts, playlists, search, songs, videos
from apple_music import schemas as S
from schema_fields import load_query
from scraper_errors import BadRequest, NotFound


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The query as unicode strings (bottle 0.12's .get() hands back latin-1
    decoded bytes, so a UTF-8 "Beyoncé" would arrive as "BeyoncÃ©")."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def _page_link(params, page):
    if not page:
        return None
    query = {k: v for k, v in params.items() if v not in (None, "")}
    query["page"] = page
    return f"{request.urlparts.scheme}://{request.urlparts.netloc}{request.path}?{urlencode(query)}"


def paginate(result, params):
    """Lift the scraper's `pagination` block into the flat shape the hosted
    API returns: count / per_page / current_page / total_pages / next /
    previous first, then the data."""
    pagination = result.pop("pagination", None) or {}
    page = int(pagination.get("page") or params.get("page") or 1)
    total_pages = int(pagination.get("total_pages") or 0)
    out = {
        "count": pagination.get("total_count"),
        "per_page": pagination.get("items_per_page"),
        "current_page": page,
        "total_pages": total_pages,
        "next": _page_link(params, page + 1 if page < total_pages else None),
        "previous": _page_link(params, page - 1 if page > 1 else None),
    }
    out.update(result)
    return out


def call(label, schema, fn, paginated=False):
    """Validate the query, run the scraper, map errors: bad params -> 400,
    missing entity -> 404, transport/blocks -> 500."""
    params = query_dict()
    data, error = load_query(schema, params)
    if error:
        return json_response(error, 400)
    try:
        result = fn(**data)
    except ValueError as e:                # bad id / params (unknown genre, …)
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:                # upstream rejected the request (unknown country, …)
        return json_response({"error": f"apple music rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Exception as e:                 # retries exhausted / blocked
        return json_response({"error": f"apple music {label} failed: {e}"}, 500)
    return json_response(paginate(result, params) if paginated else result)


def mount(path, schema, fn, paginated=False):
    """Serve an endpoint at /path and /apple-music/path."""
    def handler():
        return call(path.strip("/"), schema, fn, paginated)
    handler.__name__ = "apple_music_" + path.strip("/").replace("/", "_").replace("-", "_")
    route(path, method="GET")(handler)
    route("/apple-music" + path, method="GET")(handler)


P = True   # paginated
ENDPOINTS = [
    ("/songs/details", S.SongSchema, songs.details, False),
    ("/search/auto-complete", S.AutoCompleteSchema, search.auto_complete, False),
    ("/search/all", S.SearchAllSchema, search.search_all, False),
    ("/search/songs", S.SearchSchema, search.search_songs, P),
    ("/search/albums", S.SearchSchema, search.search_albums, P),
    ("/search/artists", S.SearchSchema, search.search_artists, P),
    ("/search/playlists", S.SearchSchema, search.search_playlists, P),
    ("/search/music-videos", S.SearchSchema, search.search_music_videos, P),
    ("/search/stations", S.SearchSchema, search.search_stations, P),
    ("/search/curators", S.SearchSchema, search.search_curators, P),
    ("/search/labels", S.SearchSchema, search.search_labels, P),
    ("/songs/batch", S.SongBatchSchema, songs.batch, False),
    ("/albums/details", S.AlbumSchema, albums.details, False),
    ("/albums/related", S.AlbumSchema, albums.related, False),
    ("/artists/details", S.ArtistSchema, artists.details, False),
    ("/artists/top-songs", S.ArtistPagedSchema, artists.top_songs, P),
    ("/artists/albums", S.ArtistAlbumsSchema, artists.albums, P),
    ("/artists/music-videos", S.ArtistVideosSchema, artists.music_videos, P),
    ("/artists/playlists", S.ArtistPlaylistsSchema, artists.playlists, P),
    ("/artists/similar", S.ArtistPagedSchema, artists.similar, P),
    ("/playlists/details", S.PlaylistSchema, playlists.details, False),
    ("/playlists/tracks", S.PlaylistTracksSchema, playlists.tracks, P),
    ("/music-videos/details", S.VideoSchema, videos.details, False),
    ("/charts/top-songs", S.ChartSchema, charts.top_songs, P),
    ("/charts/top-albums", S.ChartSchema, charts.top_albums, P),
    ("/charts/top-playlists", S.ChartSchema, charts.top_playlists, P),
    ("/charts/top-music-videos", S.ChartSchema, charts.top_music_videos, P),
    ("/charts/daily-top-100", S.DailyTop100Schema, charts.daily_top_100, False),
    ("/charts/daily-top-100-list", S.LangOnlySchema, charts.daily_top_100_list, False),
    ("/charts/city-top-25", S.CityChartSchema, charts.city_top_25, False),
    ("/charts/city-charts-list", S.LangOnlySchema, charts.city_charts_list, False),
    ("/browse", S.LocaleSchema, browse.browse, False),
    ("/browse/section", S.SectionSchema, browse.section, P),
    ("/browse/new-releases", S.BrowseSectionSchema, browse.new_releases, P),
    ("/browse/recent-releases", S.BrowseSectionSchema, browse.recent_releases, P),
    ("/browse/best-new-songs", S.BrowseSectionSchema, browse.best_new_songs, P),
    ("/browse/trending-songs", S.BrowseSectionSchema, browse.trending_songs, P),
    ("/browse/coming-soon", S.BrowseSectionSchema, browse.coming_soon, P),
    ("/browse/updated-playlists", S.BrowseSectionSchema, browse.updated_playlists, P),
    ("/browse/popular", S.BrowseSectionSchema, browse.popular, P),
    ("/browse/dj-mixes", S.BrowseSectionSchema, browse.dj_mixes, P),
    ("/radio", S.LocaleSchema, browse.radio, False),
    ("/stations/live", S.LocaleSchema, catalog.live_stations, False),
    ("/stations/details", S.StationSchema, catalog.station_details, False),
    ("/genres", S.LocaleSchema, catalog.genres, False),
    ("/genres/details", S.GenreSchema, catalog.genre_details, False),
    ("/labels/details", S.LabelSchema, catalog.label_details, False),
    ("/labels/releases", S.LabelReleasesSchema, catalog.label_releases, P),
    ("/curators/details", S.CuratorSchema, catalog.curator_details, False),
    ("/curators/playlists", S.CuratorPlaylistsSchema, catalog.curator_playlists, P),
    ("/countries", S.LangOnlySchema, catalog.countries, False),
]

for _path, _schema, _fn, _paginated in ENDPOINTS:
    mount(_path, _schema, _fn, _paginated)


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": [e[0] for e in ENDPOINTS]})
