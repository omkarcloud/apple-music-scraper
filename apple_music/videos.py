"""/apple-music/music-videos/details."""
from apple_music import parsers as P
from apple_music.fetch import resource
from apple_music.shared import storefront


def details(video, country=None, lang=None):
    """A music video with its artists, album, the songs it features and the
    "more by artist" / "more in genre" shelves."""
    sf = storefront(country, video)
    obj = resource(sf, "music-videos", video["id"], {
        "include": "artists,albums,songs,genres", "views": "more-by-artist,more-in-genre",
        "extend": "editorialNotes,editorialArtwork",
    }, lang=lang)
    albums = P.rel(obj, "albums")
    genres = P.rel(obj, "genres")
    out = P.music_video(obj)
    out.update({
        "primary_genre": P.genre(genres[0]) if genres else None,
        "artists": P.items(P.rel(obj, "artists")),
        "album": P.album(albums[0]) if albums else None,
        "songs": P.items(P.rel(obj, "songs")),
        "more_by_artist": P.items(P.view(obj, "more-by-artist")),
        "more_in_genre": P.items(P.view(obj, "more-in-genre")),
    })
    return out
