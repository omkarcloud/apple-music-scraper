"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. The functions live in apple_music/ (songs, albums, artists,
playlists, videos, charts, browse, search, catalog).
"""
import json
import os

from apple_music import charts, refs, search, songs

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a song id, an ISRC or any music.apple.com song link
    save("song_anti_hero.json", songs.details(refs.resolve_song("1649434293")))

    # 25 per page; also search_albums, search_artists, search_playlists, ...
    save("search_taylor_swift.json", search.search_songs("taylor swift"))

    # today's Top 100 — "global" or any country code
    save("daily_top_100_us.json", charts.daily_top_100("us"))
