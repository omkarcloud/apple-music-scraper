# 🎵 Apple Music Scraper

Apple Music Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Apple Music data for free.

## ✨ What Can I Get?

- 🎵 **Full details on 100M+ songs** — ISRC, composers, 30-second previews, lyrics excerpts & lossless/Dolby Atmos flags
- 🎤 **Every artist, album & playlist** — bios, full discographies, tracklists with UPC & label, top songs, similar artists
- 📈 **Charts in 115+ countries** — Top Songs, Albums, Playlists & Videos by genre, Daily Top 100, 100+ City Top 25s
- 🔥 **New releases & editorial picks** — Best New Songs, New This Week, Coming Soon, radio shows & live stations

## 🎥 Example: A Full Apple Music Song

```json
{
  "id": "1649434293",
  "name": "Anti-Hero",
  "link": "https://music.apple.com/us/album/anti-hero/1649434004?i=1649434293",
  "artist_name": "Taylor Swift",
  "album_name": "Midnights",
  "composer_name": "Taylor Swift & Jack Antonoff",
  "isrc": "USUG12205736",
  "release_date": "2022-10-21",
  "duration": "3:20",
  "genres": ["Pop", "Music"],
  "audio_traits": ["atmos", "lossless", "lossy_stereo", "spatial"],
  "has_time_synced_lyrics": true,
  "is_apple_digital_master": true,
  "lyrics_excerpt": "I have this thing where I get older, but just never wiser\nMidnights become my afternoons",
  "preview_link": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/1d/56/2a/1d562a07-dc5f-a9c0-1f36-2051a8c14eb7/mzaf_4558921924675045578.plus.aac.ep.m4a",
  "artwork": { "link": "https://is1-ssl.mzstatic.com/image/thumb/Music112/v4/3d/01/f2/3d01f2e5-5a08-835f-3d30-d031720b2b80/22UM1IM07364.rgb.jpg/3000x3000bb.jpg", "width": 3000, "height": 3000 },
  "album": { "id": "1649434004", "name": "Midnights", "record_label": "Taylor Swift", "upc": "00602448762689", "release_date": "2022-10-21", "track_count": 14 },
  "artists": [
    { "id": "159260351", "name": "Taylor Swift", "origin": "West Reading, PA, United States", "born_or_formed": "1989-12-13" }
  ],
  "primary_genre": { "id": "14", "name": "Pop" },
  "radio_station": { "id": "ra.1649434293", "name": "Anti-Hero Station" }
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Apple Music Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/apple-music-scraper
cd apple-music-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/songs/details?song=1649434293"
```

```json
{
  "id": "1649434293",
  "name": "Anti-Hero",
  "artist_name": "Taylor Swift",
  "album_name": "Midnights",
  "composer_name": "Taylor Swift & Jack Antonoff",
  "isrc": "USUG12205736",
  "release_date": "2022-10-21",
  "duration": "3:20",
  "track_number": 3,
  "genres": ["Pop", "Music"],
  "audio_traits": ["atmos", "lossless", "lossy_stereo", "spatial"],
  "has_lyrics": true,
  "has_time_synced_lyrics": true,
  "is_sing_along_available": true,
  "preview_link": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/1d/56/2a/1d562a07-dc5f-a9c0-1f36-2051a8c14eb7/mzaf_4558921924675045578.plus.aac.ep.m4a",
  "album": { "id": "1649434004", "name": "Midnights", "upc": "00602448762689", "track_count": 14 },
  "artists": [{ "id": "159260351", "name": "Taylor Swift" }]
}
```

All 51 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

51 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Song Details | `/songs/details` | Everything about one song — by ID, ISRC or link |
| Autocomplete | `/search/auto-complete` | Search-box suggestions plus top matching songs, albums, artists |
| Search All | `/search/all` | Top results plus every type in one call |
| Search Songs / Albums / Artists / Playlists | `/search/songs`, `/search/albums`, `/search/artists`, `/search/playlists` | Up to 50 results per page with full details |
| Search Music Videos / Stations / Curators / Labels | `/search/music-videos`, `/search/stations`, `/search/curators`, `/search/labels` | Videos, radio, curators and record labels by keyword |
| Songs Batch | `/songs/batch` | Up to 100 songs in one call |
| Album Details | `/albums/details` | Every track plus UPC, label and editorial notes — by ID, UPC or link |
| Album Related | `/albums/related` | Other versions, more by the artist, similar albums |
| Artist Details | `/artists/details` | The whole artist page: bio, top songs, discography, videos |
| Artist Top Songs / Albums / Music Videos / Playlists | `/artists/top-songs`, `/artists/albums`, `/artists/music-videos`, `/artists/playlists` | An artist's full catalog, paged and filterable by type |
| Similar Artists | `/artists/similar` | Artists Apple Music recommends alongside them |
| Playlist Details / Tracks | `/playlists/details`, `/playlists/tracks` | Curator, description and every track by position |
| Music Video Details | `/music-videos/details` | ISRC, 4K/HDR flags, preview stream and related videos |
| Top Songs / Albums / Playlists / Music Videos | `/charts/top-songs`, `/charts/top-albums`, `/charts/top-playlists`, `/charts/top-music-videos` | Ranked charts for any country, overall or per genre |
| Daily Top 100 | `/charts/daily-top-100`, `/charts/daily-top-100-list` | Today's Top 100, global or for 115+ countries |
| City Top 25 | `/charts/city-top-25`, `/charts/city-charts-list` | Today's Top 25 in 100+ cities |
| Browse Page / Section | `/browse`, `/browse/section` | Every Browse shelf, or all items in one shelf |
| New Releases, Best New Songs & more | `/browse/new-releases`, `/browse/recent-releases`, `/browse/best-new-songs`, `/browse/trending-songs`, `/browse/coming-soon`, `/browse/updated-playlists`, `/browse/popular`, `/browse/dj-mixes` | Apple Music's editorial picks, paged |
| Radio Page / Stations | `/radio`, `/stations/live`, `/stations/details` | Live radio, shows, episodes and broadcasters |
| Genres | `/genres`, `/genres/details` | Genres per country and each genre's playlists |
| Labels | `/labels/details`, `/labels/releases` | Record label profile with latest and top releases |
| Curators | `/curators/details`, `/curators/playlists` | Curators and radio shows with all their playlists |
| Countries | `/countries` | All 167 Apple Music countries and their languages |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-apple-music-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-apple-music-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-apple-music-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/songs/details",
    params={"song": "1649434293"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Apple Music Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Apple%20Music%20Scraper%20API.)

[![Ask Us by Email about Apple Music Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Apple%20Music%20Scraper%20API&body=I%20need%20help%20using%20the%20Apple%20Music%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/apple-music-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/apple-music-scraper)
