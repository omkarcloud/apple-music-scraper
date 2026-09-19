"""Marshmallow request schemas for every /apple-music/* route.

Generic fields live in the shared top-level schema_fields.py; this module
adds the Apple Music resolvers and the per-route schemas. Every schema's
load() output is the kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrLinkField convention, never a
sibling `url`/`id` pair): `song` takes an id, an ISRC or a link; `album` an
id, a UPC/EAN or a link; `artist` / `playlist` / `video` / `station` /
`curator` / `label` an id or a link; `genre` an id or a name (refs.py).

Every route takes `country` (ISO code of the Apple Music storefront,
default: the pasted link's storefront, else US) and `lang` (a language tag
such as en-US, fr-FR, ja; default: the storefront's own language).
"""
from marshmallow import ValidationError, fields, validate

from schema_fields import (COUNTRY_CODES, BaseSchema, ChoiceField, CountryCodeField,
                           LanguageCodeField, PageField, PageSizeField, QueryField, RefField,
                           StrippedString)
from apple_music import refs


# ---- id-or-link fields -------------------------------------------------------------

class SongRefField(RefField):
    resolver = staticmethod(refs.resolve_song)


class AlbumRefField(RefField):
    resolver = staticmethod(refs.resolve_album)


class ArtistRefField(RefField):
    resolver = staticmethod(refs.resolve_artist)


class PlaylistRefField(RefField):
    resolver = staticmethod(refs.resolve_playlist)


class VideoRefField(RefField):
    resolver = staticmethod(refs.resolve_music_video)


class StationRefField(RefField):
    resolver = staticmethod(refs.resolve_station)


class CuratorRefField(RefField):
    resolver = staticmethod(refs.resolve_curator)


class LabelRefField(RefField):
    resolver = staticmethod(refs.resolve_label)


class GenreRefField(RefField):
    resolver = staticmethod(refs.resolve_genre)


class SongListField(fields.Field):
    """Comma-separated song ids or links (max 100) -> list of unique ids."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        values = [v.strip() for v in str(value).split(",") if v.strip()]
        if not values:
            raise ValidationError("Give at least one song id.")
        if len(values) > 100:
            raise ValidationError("At most 100 songs.")
        try:
            return refs.resolve_song_list(values)
        except ValueError as e:
            raise ValidationError(str(e))


class SectionIdField(StrippedString):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        kwargs.setdefault("validate", validate.Regexp(r"^\d{4,12}$", error="Must be a section id (see_all_id from /apple-music/browse)."))
        super().__init__(**kwargs)


class RegionField(StrippedString):
    """'global' or an ISO country code (lower-cased)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", "global")
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return "global"
        if value.lower() == "global":
            return "global"
        if value.upper() not in COUNTRY_CODES:
            raise ValidationError("Must be global or a 2-letter ISO country code (US, GB, IN, ...).")
        return value.lower()


def _page():
    return PageField(max_page=500)


# ---- base schemas -------------------------------------------------------------------

class LocaleSchema(BaseSchema):
    country = CountryCodeField()
    lang = LanguageCodeField()


class LangOnlySchema(BaseSchema):
    lang = LanguageCodeField()


# ---- search -------------------------------------------------------------------------

class AutoCompleteSchema(LocaleSchema):
    query = QueryField(max_length=100)


class SearchAllSchema(LocaleSchema):
    query = QueryField()
    limit = PageSizeField(default=5, max_size=25)


class SearchSchema(LocaleSchema):
    query = QueryField()
    page = _page()
    limit = PageSizeField(default=25, max_size=50)


# ---- songs / albums / videos ----------------------------------------------------------

class SongSchema(LocaleSchema):
    song = SongRefField()


class SongBatchSchema(LocaleSchema):
    songs = SongListField()


class AlbumSchema(LocaleSchema):
    album = AlbumRefField()


class VideoSchema(LocaleSchema):
    video = VideoRefField()


# ---- artists -------------------------------------------------------------------------

class ArtistSchema(LocaleSchema):
    artist = ArtistRefField()


class ArtistPagedSchema(ArtistSchema):
    page = _page()
    limit = PageSizeField(default=20, max_size=100)


class ArtistAlbumsSchema(ArtistPagedSchema):
    type = ChoiceField(list(refs.ARTIST_ALBUM_TYPES), load_default="all")


class ArtistVideosSchema(ArtistPagedSchema):
    type = ChoiceField(list(refs.ARTIST_VIDEO_TYPES), load_default="all")


class ArtistPlaylistsSchema(ArtistPagedSchema):
    type = ChoiceField(list(refs.ARTIST_PLAYLIST_TYPES), load_default="artist")


# ---- playlists -----------------------------------------------------------------------

class PlaylistSchema(LocaleSchema):
    playlist = PlaylistRefField()


class PlaylistTracksSchema(PlaylistSchema):
    page = _page()
    limit = PageSizeField(default=100, max_size=100)


# ---- charts --------------------------------------------------------------------------

class ChartSchema(LocaleSchema):
    genre = GenreRefField(required=False, load_default=None)
    page = PageField(max_page=20)
    limit = PageSizeField(default=50, max_size=100)


class DailyTop100Schema(LangOnlySchema):
    region = RegionField()


class CityChartSchema(LangOnlySchema):
    city = QueryField(max_length=80)


# ---- browse / radio --------------------------------------------------------------------

class BrowseSectionSchema(LocaleSchema):
    sort = ChoiceField(list(refs.ROOM_SORTS))
    page = _page()
    limit = PageSizeField(default=50, max_size=100)


class SectionSchema(BrowseSectionSchema):
    section = SectionIdField()


# ---- genres / labels / curators / stations ----------------------------------------------

class GenreSchema(LocaleSchema):
    genre = GenreRefField()


class LabelSchema(LocaleSchema):
    label = LabelRefField()


class LabelReleasesSchema(LabelSchema):
    type = ChoiceField(["latest", "top"], load_default="latest")
    page = _page()
    limit = PageSizeField(default=20, max_size=100)


class CuratorSchema(LocaleSchema):
    curator = CuratorRefField()


class CuratorPlaylistsSchema(CuratorSchema):
    page = _page()
    limit = PageSizeField(default=25, max_size=100)


class StationSchema(LocaleSchema):
    station = StationRefField()
