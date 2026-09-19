"""Apple Music payload normalizers: amp-api JSON:API resources -> one clean
snake_case shape per resource type.

Conventions: `link` for web URLs, `artwork` {link, template_link, width,
height, background_color} for every image, `description` {title, tagline,
short, full} for Apple's editorial copy (plain text — the HTML variant is
stripped), `duration_ms` + `duration` ("3:47"), `is_*` / `has_*` booleans,
ISO dates (YYYY-MM-DD) and UTC datetimes, null for missing.

Upstream fields dropped on purpose (and why):
  * playParams (id + kind duplicate `id`/type; versionHash/stationHash are
    player-internal), href / relationship hrefs (API paths that need the
    token), meta.metrics.dataSetId (tracking).
  * extendedAssetUrls (song HLS / m4p streams: DRM-encrypted, access-keyed,
    unplayable outside a subscriber's player), radioUrl (itsradio:// app
    deep link), supportedDrms, appBundleId, movie `offers` (store purchase
    params), movieClips / supportedLocales (player internals).
  * artwork textColor1-4 / hasP3 / gradient / defaultCropCode (presentation
    only; bgColor is kept as background_color), artist `hero` (the same
    image as `artwork`), editorialElementKind / doNotFilter / emphasize /
    featureFirstElement (page-layout switches).
  * editorialNotes when plainEditorialNotes exists (same text with HTML).
"""
import html as _html
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_CAMEL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")
_ALBUM_ID_RE = re.compile(r"/album/[^/]+/(\d+)")
_CJK_DATE_RE = re.compile(r"^(\d{4})年(?:(\d{1,2})月)?(?:(\d{1,2})日)?$")


# ---- value helpers ----------------------------------------------------------

def clean(value):
    """'' / [] / {} -> None (uniform nulls)."""
    return None if value in ("", [], {}, None) else value


def to_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def snake(text):
    """camelCase / kebab-case / spaced -> snake_case ('hasP3' -> 'has_p3')."""
    if not text:
        return None
    text = _CAMEL_2.sub(r"\1_\2", _CAMEL_1.sub(r"\1_\2", str(text)))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or None


def strip_html(text):
    """Apple's editorial HTML (<i>, <b>, <br>) -> plain text."""
    if not text or not isinstance(text, str):
        return None
    text = _BR_RE.sub("\n", text)
    text = _html.unescape(_TAG_RE.sub("", text)).replace(" ", " ")
    return text.strip() or None


def iso_date(value):
    """'2016-04-29' stays; a datetime is cut to its date; junk -> None."""
    if not value or not isinstance(value, str):
        return None
    return value[:10] if re.match(r"^\d{4}(-\d{2}(-\d{2})?)?", value) else None


def iso_datetime(value):
    """'2026-09-19T07:42:19Z' -> same (UTC, second precision)."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def human_date(value):
    """'October 24, 1986' -> '1986-10-24', 'October 1986' -> '1986-10',
    '1986' -> '1986'; any other (localised) text is returned unchanged."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    cjk = _CJK_DATE_RE.match(text)             # ja / zh: 1986年10月24日
    if cjk:
        year, month, day = cjk.groups()
        return "-".join(p for p in (year, month and month.zfill(2), day and day.zfill(2)) if p)
    for fmt, out in (("%B %d, %Y", "%Y-%m-%d"), ("%d %B %Y", "%Y-%m-%d"), ("%B %Y", "%Y-%m"), ("%Y", "%Y")):
        try:
            return datetime.strptime(text, fmt).strftime(out)
        except ValueError:
            continue
    return text


def duration_text(ms):
    """328910 -> '5:28'; 3725000 -> '1:02:05'."""
    ms = to_int(ms)
    if ms is None:
        return None
    seconds = ms // 1000               # the player truncates (328910 ms = "5:28")
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def artwork(art):
    """amp-api artwork -> {link (full size jpg), template_link ({w}x{h}
    placeholders for any size), width, height, background_color}."""
    if not isinstance(art, dict) or not art.get("url"):
        return None
    template = art["url"]
    width, height = to_int(art.get("width")), to_int(art.get("height"))
    full = template.replace("{w}", str(width or 3000)).replace("{h}", str(height or 3000))
    full = full.replace("{c}", "bb").replace("{f}", "jpg")
    bg = art.get("bgColor")
    return {
        "link": full,
        "template_link": template,
        "width": width,
        "height": height,
        "background_color": f"#{bg}" if bg else None,
    }


def editorial_artwork(attrs):
    """{bannerUber: {...}, storeFlowcase: {...}} -> {banner_uber: link, ...}."""
    out = {}
    for kind, art in (attrs.get("editorialArtwork") or {}).items():
        parsed = artwork(art)
        if parsed:
            out[snake(kind)] = parsed["link"]
    return out or None


def motion_artwork(attrs):
    """editorialVideo {motionDetailSquare: {video, previewFrame}} ->
    {motion_detail_square: {video_link, preview_link}} (HLS loops)."""
    out = {}
    for kind, video in (attrs.get("editorialVideo") or {}).items():
        if isinstance(video, dict) and video.get("video"):
            preview = artwork(video.get("previewFrame"))
            out[snake(kind)] = {"video_link": video["video"],
                                "preview_link": preview["link"] if preview else None}
    return out or None


def description(attrs, field="plainEditorialNotes"):
    """plainEditorialNotes (or editorialNotes / description stripped of HTML)
    -> {title, tagline, short, full}; None when there is no copy at all."""
    notes = attrs.get(field) or attrs.get("editorialNotes") or attrs.get("description") or {}
    if isinstance(notes, str):
        notes = {"standard": notes}
    if not isinstance(notes, dict):
        return None
    out = {
        "title": strip_html(notes.get("name")),
        "tagline": strip_html(notes.get("tagline")),
        "short": strip_html(notes.get("short")),
        "full": strip_html(notes.get("standard")),
    }
    return out if any(out.values()) else None


def rating_flags(attrs):
    rating = attrs.get("contentRating")
    return rating == "explicit", rating == "clean"


def traits(values):
    return [snake(v) for v in values or [] if v] or None


def preview_link(attrs):
    for preview in attrs.get("previews") or []:
        if isinstance(preview, dict) and (preview.get("url") or preview.get("hlsUrl")):
            return preview.get("url") or preview.get("hlsUrl")
    return None


def album_id_from_link(link):
    m = _ALBUM_ID_RE.search(link or "")
    return m.group(1) if m else None


def song_id_from_link(link):
    try:
        return (parse_qs(urlparse(link).query).get("i") or [None])[0]
    except Exception:
        return None


def _attrs(obj):
    return (obj or {}).get("attributes") or {}


# ---- resources --------------------------------------------------------------

def song(obj):
    a = _attrs(obj)
    explicit, clean_version = rating_flags(a)
    link = a.get("url")
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": link,
        "artist_name": a.get("artistName"),
        "album_id": album_id_from_link(link),
        "album_name": a.get("albumName"),
        "album_artist_name": a.get("albumArtistName"),
        "composer_name": a.get("composerName"),
        "isrc": a.get("isrc"),
        "release_date": iso_date(a.get("releaseDate")),
        "duration_ms": to_int(a.get("durationInMillis")),
        "duration": duration_text(a.get("durationInMillis")),
        "track_number": to_int(a.get("trackNumber")),
        "disc_number": to_int(a.get("discNumber")),
        "genres": clean(a.get("genreNames")),
        "audio_language": a.get("audioLocale"),
        "audio_traits": traits(a.get("audioTraits")),
        "is_explicit": explicit,
        "is_clean_version": clean_version,
        "has_lyrics": bool(a.get("hasLyrics")),
        "has_time_synced_lyrics": bool(a.get("hasTimeSyncedLyrics")),
        "is_apple_digital_master": bool(a.get("isAppleDigitalMaster")),
        "is_mastered_for_itunes": bool(a.get("isMasteredForItunes")),
        "is_sing_along_available": bool(a.get("isVocalAttenuationAllowed")),
        "lyrics_excerpt": clean(a.get("lyricsExcerpt")),
        "preview_link": preview_link(a),
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
    }


def release_type(a):
    name = a.get("name") or ""
    if a.get("isSingle"):
        return "single" if not name.endswith(" - EP") else "ep"
    if name.endswith(" - EP"):
        return "ep"
    if a.get("isCompilation"):
        return "compilation"
    return "album"


def album(obj):
    a = _attrs(obj)
    explicit, clean_version = rating_flags(a)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "artist_name": a.get("artistName"),
        "release_type": release_type(a),
        "record_label": a.get("recordLabel"),
        "copyright": a.get("copyright"),
        "upc": a.get("upc"),
        "release_date": iso_date(a.get("releaseDate")),
        "track_count": to_int(a.get("trackCount")),
        "genres": clean(a.get("genreNames")),
        "audio_traits": traits(a.get("audioTraits")),
        "is_single": bool(a.get("isSingle")),
        "is_compilation": bool(a.get("isCompilation")),
        "is_complete": bool(a.get("isComplete")),
        "is_prerelease": bool(a.get("isPrerelease")),
        "is_mastered_for_itunes": bool(a.get("isMasteredForItunes")),
        "is_explicit": explicit,
        "is_clean_version": clean_version,
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
        "editorial_artwork": editorial_artwork(a),
        "motion_artwork": motion_artwork(a),
        "classical_link": a.get("classicalUrl"),
    }


def artist(obj):
    a = _attrs(obj)
    group = a.get("isGroup")
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "genres": clean(a.get("genreNames")),
        "origin": clean(a.get("origin")),
        "born_or_formed": human_date(a.get("bornOrFormed")),
        "is_group": group if isinstance(group, bool) else None,
        "bio": strip_html(a.get("artistBio")),
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
        "editorial_artwork": editorial_artwork(a),
        "motion_artwork": motion_artwork(a),
    }


def playlist(obj):
    a = _attrs(obj)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "curator_name": a.get("curatorName"),
        "playlist_type": snake(a.get("playlistType")),
        "editorial_kind": snake(a.get("editorialPlaylistKind")),
        "editorial_sub_kind": snake(a.get("editorialPlaylistSubKind")),
        "track_count": to_int(a.get("trackCount")),
        "artist_names": strip_html(a.get("artistNames")),
        "audio_traits": traits(a.get("audioTraits")),
        "is_chart": bool(a.get("isChart")),
        "has_collaboration": bool(a.get("hasCollaboration")),
        "is_sing_along_available": bool(a.get("supportsSing")),
        "last_modified_at": iso_datetime(a.get("lastModifiedDate")),
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
        "editorial_artwork": editorial_artwork(a),
        "motion_artwork": motion_artwork(a),
    }


def music_video(obj):
    a = _attrs(obj)
    explicit, clean_version = rating_flags(a)
    preview = next((p for p in a.get("previews") or [] if isinstance(p, dict)), {})
    video_traits = a.get("videoTraits") or []
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "artist_name": a.get("artistName"),
        "album_name": a.get("albumName"),
        "album_artist_name": a.get("albumArtistName"),
        "isrc": a.get("isrc"),
        "release_date": iso_date(a.get("releaseDate")),
        "duration_ms": to_int(a.get("durationInMillis")),
        "duration": duration_text(a.get("durationInMillis")),
        "track_number": to_int(a.get("trackNumber")),
        "disc_number": to_int(a.get("discNumber")),
        "genres": clean(a.get("genreNames")),
        "video_traits": traits(video_traits),
        "has_4k": bool(a.get("has4K")),
        "has_hdr": bool(a.get("hasHDR")),
        "is_explicit": explicit,
        "is_clean_version": clean_version,
        "preview": {
            "video_link": preview.get("hlsUrl") or preview.get("url"),
            "artwork": artwork(preview.get("artwork")),
        } if preview else None,
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
    }


def station(obj):
    a = _attrs(obj)
    explicit, _ = rating_flags(a)
    air = a.get("airTime") or {}
    band, frequency = a.get("band"), a.get("frequency")
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "kind": snake(a.get("kind")),
        "provider_name": a.get("stationProviderName"),
        "media_kind": snake(a.get("mediaKind")),
        "stream_type": snake(a.get("streamingRadioSubType")),
        "episode_number": to_int(a.get("episodeNumber")),
        "air_time": {"start": iso_datetime(air.get("start")), "end": iso_datetime(air.get("end"))} if air else None,
        "duration_ms": to_int(a.get("durationInMillis")),
        "duration": duration_text(a.get("durationInMillis")),
        "broadcast": {"band": band, "frequency": frequency} if (band or frequency) else None,
        "is_live": bool(a.get("isLive")),
        "is_explicit": explicit,
        "requires_subscription": bool(a.get("requiresSubscription")),
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
        "motion_artwork": motion_artwork(a),
    }


def curator(obj):
    a = _attrs(obj)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "short_name": a.get("shortName"),
        "curator_type": "apple" if obj.get("type") == "apple-curators" else "external",
        "kind": snake(a.get("kind")),
        "show_host_name": a.get("showHostName"),
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
        "editorial_artwork": editorial_artwork(a),
    }


def label(obj):
    a = _attrs(obj)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "description": description(a, field="description"),
        "artwork": artwork(a.get("artwork")),
        "editorial_artwork": editorial_artwork(a),
    }


def genre(obj):
    a = _attrs(obj)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "parent_id": a.get("parentId"),
        "parent_name": a.get("parentName"),
    }


def uploaded_video(obj):
    a = _attrs(obj)
    ratings = a.get("contentRatingsBySystem") or {}
    riaa = (ratings.get("riaa") or {}).get("name")
    links = {snake(k): v for k, v in (a.get("assetTokens") or {}).items() if isinstance(v, str)}
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("postUrl") or a.get("url"),
        "artist_name": a.get("uploadingArtistName") or a.get("artistName"),
        "upload_date": iso_date(a.get("uploadDate")),
        "duration_ms": to_int(a.get("durationInMilliseconds")),
        "duration": duration_text(a.get("durationInMilliseconds")),
        "is_explicit": riaa == "Explicit",
        "video_links": links or None,
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
    }


def music_movie(obj):
    a = _attrs(obj)
    ratings = a.get("contentRatingsBySystem") or {}
    rating = next((r.get("name") for r in ratings.values() if isinstance(r, dict) and r.get("name")), None)
    return {
        "id": obj.get("id"),
        "name": a.get("name"),
        "link": a.get("url"),
        "artist_name": a.get("artistName"),
        "release_date": iso_date(a.get("releaseDate")),
        "genres": clean(a.get("genreNames")),
        "studio_name": a.get("studioName"),
        "copyright": a.get("copyright"),
        "content_rating": rating,
        "description": description(a),
        "artwork": artwork(a.get("artwork")),
    }


def country(obj):
    a = _attrs(obj)
    return {
        "country_code": (obj.get("id") or "").upper() or None,
        "name": a.get("name"),
        "default_language": a.get("defaultLanguageTag"),
        "supported_languages": clean(a.get("supportedLanguageTags")),
        "explicit_content_policy": snake(a.get("explicitContentPolicy")),
    }


PARSERS = {
    "songs": ("song", song),
    "library-songs": ("song", song),
    "albums": ("album", album),
    "artists": ("artist", artist),
    "playlists": ("playlist", playlist),
    "music-videos": ("music_video", music_video),
    "stations": ("station", station),
    "apple-curators": ("curator", curator),
    "curators": ("curator", curator),
    "record-labels": ("label", label),
    "genres": ("genre", genre),
    "uploaded-videos": ("uploaded_video", uploaded_video),
    "music-movies": ("music_movie", music_movie),
    "storefronts": ("country", country),
}


def item(obj, typed=True):
    """Any resource -> its shape; typed=True prefixes a `type` key (for
    mixed lists: search top results, browse sections). Unknown resource
    types keep id/name/link so a new Apple type never crashes a list."""
    if not isinstance(obj, dict):
        return None
    kind, parser = PARSERS.get(obj.get("type"), (snake(obj.get("type")), None))
    if parser is None:
        a = _attrs(obj)
        body = {"id": obj.get("id"), "name": a.get("name") or a.get("title"), "link": a.get("url")}
    else:
        body = parser(obj)
    return {"type": kind, **body} if typed else body


def items(objs, typed=False):
    return [x for x in (item(o, typed) for o in objs or []) if x]


def rel(obj, name):
    """A relationship's data list (resolved objects only)."""
    return [o for o in (((obj or {}).get("relationships") or {}).get(name) or {}).get("data") or []
            if isinstance(o, dict) and o.get("attributes")]


def view(obj, name):
    """A view's data list."""
    return [o for o in (((obj or {}).get("views") or {}).get(name) or {}).get("data") or []
            if isinstance(o, dict)]


def view_title(obj, name):
    return ((((obj or {}).get("views") or {}).get(name) or {}).get("attributes") or {}).get("title")


def view_has_more(obj, name):
    return bool((((obj or {}).get("views") or {}).get(name) or {}).get("next"))


# ---- editorial pages ---------------------------------------------------------

def _element_items(el):
    """An editorial element's resources. Hero shelves (featured banners, "On
    Air Now") nest one element per banner, each with its own badge/tagline."""
    rels = el.get("relationships") or {}
    out = items((rels.get("contents") or {}).get("data"), typed=True)
    for child in (rels.get("children") or {}).get("data") or []:
        ca = _attrs(child)
        for resource in items(((child.get("relationships") or {}).get("contents") or {}).get("data"), typed=True):
            resource["promo_badge"] = clean(ca.get("designBadge"))
            resource["promo_text"] = clean(ca.get("designTag"))
            out.append(resource)
    return out


def section(el):
    """One editorial shelf -> {id, title, content_types, items, see_all_id}."""
    a = _attrs(el)
    rels = el.get("relationships") or {}
    room = ((rels.get("room") or {}).get("data") or [{}])[0]
    found = _element_items(el)
    return {
        "id": el.get("id"),
        "title": a.get("name") or a.get("title"),
        "content_types": content_types(a.get("resourceTypes"), found),
        "display_style": snake(a.get("displayStyle")),
        "see_all_id": room.get("id"),
        "items": found,
    }


def content_types(resource_types, found=()):
    """amp-api resource types ("uploaded-videos") -> the singular `type`
    names items carry ("uploaded_video"); falls back to the items' own."""
    out = []
    for t in resource_types or []:
        name = PARSERS.get(t, (snake(t), None))[0]
        if name not in out:
            out.append(name)
    for x in found:
        if not resource_types and x.get("type") and x["type"] not in out:
            out.append(x["type"])
    return out or None


def grouping_sections(body, tab_index=0):
    """An editorial grouping (the Browse / Radio / genre page) -> its shelves.
    Link-only shelves ("More to Explore") come back as `links`."""
    data = ((body or {}).get("data") or [{}])[0]
    tabs = ((data.get("relationships") or {}).get("tabs") or {}).get("data") or []
    if not tabs:
        return [], []
    tab = tabs[min(tab_index, len(tabs) - 1)]
    sections, links = [], []
    for el in ((tab.get("relationships") or {}).get("children") or {}).get("data") or []:
        a = _attrs(el)
        if a.get("links"):
            links.extend({"label": l.get("label"), "link": l.get("url")}
                         for l in a["links"] if isinstance(l, dict) and l.get("url"))
            continue
        parsed = section(el)
        if parsed["items"]:
            if not parsed["title"] and "promo_badge" in parsed["items"][0]:
                parsed["title"] = "Featured"
            sections.append(parsed)
    return sections, links


def room_info(obj):
    a = _attrs(obj)
    return {
        "id": obj.get("id"),
        "title": a.get("title") or a.get("name"),
        "content_types": content_types(a.get("resourceTypes")),
        "sort_options": [SORT_NAMES.get(s, snake(s)) for s in a.get("sorts") or []] or None,
        "default_sort": SORT_NAMES.get(a.get("defaultSort"), snake(a.get("defaultSort"))),
        "last_modified_at": iso_datetime(a.get("lastModifiedDate")),
    }


SORT_NAMES = {"featured": "featured", "releaseDate": "release-date", "alphabet": "name"}


# ---- pagination ---------------------------------------------------------------

def pagination(page, per_page, has_more, total_count=None):
    """The block route_glue.paginate() lifts into the flat gateway shape.
    amp-api pages by `next` links without totals, so total_pages is
    "this page + 1" while more exist (total_count stays null)."""
    if total_count is not None and per_page:
        total_pages = (int(total_count) + int(per_page) - 1) // int(per_page)
    else:
        total_pages = page + 1 if has_more else page
    return {"page": page, "items_per_page": per_page,
            "total_pages": total_pages, "total_count": total_count}
