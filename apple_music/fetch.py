"""Apple Music transport: plain curl_cffi with browser-impersonated TLS
against the same JSON API the music.apple.com web player calls. No browser,
no cookies, no login, no proxy needed (validated 2026-09-19 from direct
Indian egress; every storefront is reachable from any IP because the
storefront is a path segment, not a geo check).

How the web player authenticates, and how this module copies it:

  1. Any music.apple.com page (even the 4 KB 404 page) links the app bundle
     `/assets/index~<hash>.js`.
  2. That bundle embeds three ES256 JWTs. The one whose payload says
     `"iss": "AMPWebPlay"` (header kid "WebPlayKid") is the developer token
     the player sends as `Authorization: Bearer …`. It lives ~70 days
     (iat -> exp) and is identical for every visitor.
  3. With that token plus `Origin: https://music.apple.com`, the catalog
     host https://amp-api.music.apple.com answers anonymously:
       /v1/catalog/{storefront}/{songs|albums|artists|playlists|
           music-videos|stations|curators|apple-curators|record-labels|
           genres|charts|search|search/suggestions}
       /v1/editorial/{storefront}/{groupings|rooms}
       /v1/storefronts

The token is harvested once per process, kept until a day before it
expires, and re-harvested on the first 401. APPLE_MUSIC_TOKEN (config) can
pin one by hand.

Not reachable anonymously (need a signed-in Music-User-Token): lyrics
(`/songs/{id}/lyrics` -> 40403), library, recommendations, recently played.

FALLBACK HOOK: if amp-api ever starts refusing the harvested token from a
server IP (403 / 429 on every call), escalate the same way g2 does: add a
patchright pool with flag "apple-music" to config.CHROME_POOLS, open
https://music.apple.com/us/browse in it and run the same GETs through the
in-page fetch (patchright_driver.FetchResponse) so they carry the real
browser's TLS and cookies. Not built now: dead code while plain HTTP works.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  AppleMusicUpstreamError  transport failure / 5xx            — retryable
  AppleMusicBlocked        403 / 429 / non-JSON body          — retryable
  AppleMusicBadRequest     upstream 400 (bad country, …)      — never retried
  AppleMusicNotFound       404 / empty data                   — never retried
"""
import base64
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError

SITE = "https://music.apple.com"
API = "https://amp-api.music.apple.com"
IMPERSONATE = "chrome"
TIMEOUT = 30
FANOUT_WORKERS = 6

# The cheapest page that still links the app bundle (~4 KB vs 1.8 MB for
# /us/browse). Any 404 path renders the SPA shell.
BOOTSTRAP_URL = SITE + "/us/404"
_BUNDLE_RE = re.compile(r'src="(/assets/index~[^"]+\.js)"')
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")
TOKEN_ISSUER = "AMPWebPlay"
TOKEN_REFRESH_MARGIN = 24 * 3600   # re-harvest a day before exp

PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}


class AppleMusicUpstreamError(UpstreamError):
    """Transport failure or 5xx — retryable."""


class AppleMusicBlocked(AppleMusicUpstreamError, Blocked):
    """403 / 429 or a non-JSON body where JSON was expected — retryable."""


class AppleMusicBadRequest(BadRequest):
    """Upstream 400 (unknown storefront, bad language tag, …) — never retried."""


class AppleMusicNotFound(NotFound):
    """Resource does not exist in that storefront — never retried."""


class _TokenRejected(AppleMusicUpstreamError):
    """401: the developer token expired or was revoked — re-harvest once."""


# ---- sessions ---------------------------------------------------------------------
# One curl session per worker thread (a curl handle must not be shared).
_local = threading.local()


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        proxy = config.apple_music_proxy()
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        _local.session = sess
    return sess


def _drop_session():
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def dump_debug(name, text):
    """Write a raw response to $APPLE_MUSIC_DEBUG_DIR/<name>.txt."""
    dbg = os.environ.get("APPLE_MUSIC_DEBUG_DIR", "")
    if dbg and text:
        try:
            os.makedirs(dbg, exist_ok=True)
            with open(os.path.join(dbg, name + ".txt"), "w") as f:
                f.write(text)
        except OSError:
            pass


# ---- developer token --------------------------------------------------------------

def jwt_payload(token):
    """Decode a JWT's payload (no signature check) -> dict, {} if malformed."""
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def pick_token(bundle_js):
    """The web player's developer token out of the app bundle: the JWT
    issued by AMPWebPlay (the bundle carries two other, unrelated JWTs)."""
    candidates = list(dict.fromkeys(_JWT_RE.findall(bundle_js or "")))
    for token in candidates:
        if jwt_payload(token).get("iss") == TOKEN_ISSUER:
            return token
    return None


_token_lock = threading.Lock()
_token = {"value": None, "exp": 0}


def _harvest_token():
    sess = _session()
    try:
        page = sess.get(BOOTSTRAP_URL, headers=PAGE_HEADERS, timeout=TIMEOUT)
        match = _BUNDLE_RE.search(page.text or "")
        if not match:
            dump_debug("bootstrap", page.text)
            raise AppleMusicBlocked(f"no app bundle link on {BOOTSTRAP_URL} (HTTP {page.status_code})")
        bundle = sess.get(SITE + match.group(1), headers={"accept": "*/*", "referer": SITE + "/"},
                          timeout=60)
    except AppleMusicUpstreamError:
        raise
    except Exception as e:
        raise AppleMusicUpstreamError(f"token harvest failed: {type(e).__name__}: {e}")
    token = pick_token(bundle.text)
    if not token:
        raise AppleMusicUpstreamError("no AMPWebPlay token in the app bundle (bundle format changed?)")
    return token


def developer_token(force=False):
    """The cached developer token, harvested on first use or when forced
    (after a 401) or within a day of its expiry."""
    pinned = getattr(config, "APPLE_MUSIC_TOKEN", None)
    # A pinned token is used until it is rejected; after a forced re-harvest
    # the harvested one wins (otherwise the 401 refresh would be a no-op).
    if pinned and not force and not _token["value"]:
        return pinned
    with _token_lock:
        now = time.time()
        if force or not _token["value"] or _token["exp"] - TOKEN_REFRESH_MARGIN < now:
            token = _harvest_token()
            _token["value"] = token
            _token["exp"] = jwt_payload(token).get("exp") or now + 7 * 86400
        return _token["value"]


def _api_headers(token, lang):
    return {
        "accept": "application/json",
        "accept-language": f"{lang},en;q=0.8" if lang else "en-US,en;q=0.9",
        "authorization": f"Bearer {token}",
        "origin": SITE,
        "referer": SITE + "/",
    }


# ---- requests ---------------------------------------------------------------------

def _error_detail(body):
    try:
        errors = json.loads(body).get("errors") or []
    except Exception:
        return None
    if errors and isinstance(errors[0], dict):
        return errors[0].get("detail") or errors[0].get("title")
    return None


_KIND_NAMES = {"songs": "song", "albums": "album", "artists": "artist", "playlists": "playlist",
               "music-videos": "music video", "stations": "station", "curators": "curator",
               "apple-curators": "curator", "record-labels": "label", "genres": "genre",
               "rooms": "section", "groupings": "page"}


def not_found_message(path):
    """'/v1/catalog/us/songs/123[/…]' -> "song 123 not found in the US catalog"."""
    parts = [p for p in (path or "").split("?")[0].split("/") if p]
    if len(parts) >= 5 and parts[0] == "v1" and parts[1] in ("catalog", "editorial"):
        kind = _KIND_NAMES.get(parts[3], parts[3].rstrip("s"))
        return f"{kind} {parts[4]} not found in the {parts[2].upper()} catalog"
    return None


def _classify(resp, label):
    status = resp.status_code
    if status == 200:
        return
    detail = _error_detail(resp.text or "")
    if status == 401:
        raise _TokenRejected(f"HTTP 401 on {label}")
    if status == 404:
        raise AppleMusicNotFound(not_found_message(label) or detail or f"{label} not found")
    if status == 400:
        if detail and detail.startswith("Unknown storefront"):
            code = detail.split()[-1].strip("'\"").upper()
            raise AppleMusicBadRequest(f"Apple Music is not available in {code}; "
                                       "see /apple-music/countries")
        raise AppleMusicBadRequest(detail or f"upstream rejected {label}")
    if status in (403, 429):
        dump_debug("blocked", resp.text)
        raise AppleMusicBlocked(f"HTTP {status} on {label}")
    raise AppleMusicUpstreamError(f"HTTP {status} on {label}")


# Attributes amp-api only returns when asked via `extend`, requested on every
# catalog/editorial call so list items (search hits, chart rows, shelf items)
# carry the same fields as details: a playlist's track count and artist
# names, an artist's origin / birth date / group flag, a song's lyrics
# excerpt. `extend` applies to nested views and relationships too.
DEFAULT_EXTEND = ("artistNames", "trackCount", "isGroup", "origin", "bornOrFormed", "lyricsExcerpt")


def _with_extend(path, query):
    if not path.startswith(("/v1/catalog/", "/v1/editorial/")):
        return query
    wanted = [e for e in str(query.get("extend") or "").split(",") if e]
    wanted += [e for e in DEFAULT_EXTEND if e not in wanted]
    return {**query, "extend": ",".join(wanted)}


def api_get(path, params=None, *, lang=None, label=None):
    """GET one amp-api path (e.g. "/v1/catalog/us/songs/123") -> parsed JSON.

    `params` values that are None are dropped. Retries transport errors,
    5xx and blocks with backoff on a fresh curl session; a 401 re-harvests
    the developer token once. 400/404 raise immediately."""
    label = label or path
    query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    if lang:
        query.setdefault("l", lang)
    query = _with_extend(path, query)
    token_refreshed = False
    last = None
    attempt = 0
    while attempt < config.MAX_RETRIES:
        attempt += 1
        token = developer_token()
        try:
            resp = _session().get(API + path, params=query, headers=_api_headers(token, lang),
                                  timeout=TIMEOUT)
        except Exception as e:
            last = AppleMusicUpstreamError(f"request failed: {type(e).__name__}: {e}")
            _drop_session()
        else:
            try:
                _classify(resp, label)
                body = resp.text or ""
                if not body.lstrip().startswith("{"):
                    dump_debug("nonjson", body)
                    raise AppleMusicBlocked(f"{label} returned a non-JSON body")
                return resp.json()
            except _TokenRejected as e:
                last = e
                if token_refreshed:
                    break
                token_refreshed = True
                developer_token(force=True)
                attempt -= 1          # a token refresh is not a failed attempt
                continue
            except (AppleMusicBlocked, AppleMusicUpstreamError) as e:
                last = e
                _drop_session()
        if attempt < config.MAX_RETRIES:
            time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


def catalog_get(country, tail, params=None, *, lang=None):
    """GET /v1/catalog/{country}/{tail}."""
    return api_get(f"/v1/catalog/{country}/{tail}", params, lang=lang)


def resource(country, kind, rid, params=None, *, lang=None):
    """One catalog resource -> its `data[0]` object (NotFound when empty)."""
    body = catalog_get(country, f"{kind}/{rid}", params, lang=lang)
    data = (body or {}).get("data") or []
    if not data:
        raise AppleMusicNotFound(not_found_message(f"/v1/catalog/{country}/{kind}/{rid}"))
    return data[0]


def page_range(path, offset, limit, *, max_per_call, lang=None, params=None, key=None):
    """Fetch `limit` items starting at `offset` from a paged collection whose
    upstream page size caps at `max_per_call`, fanning out in parallel.

    `key` picks the list out of each response (default: body["data"]).
    Returns (items, has_more): has_more is True when the upstream still
    offered a `next` page after the last item fetched."""
    chunks = []
    start = offset
    while start < offset + limit:
        size = min(max_per_call, offset + limit - start)
        chunks.append((start, size))
        start += size

    def fetch(chunk):
        start, size = chunk
        query = dict(params or {})
        query.update({"offset": start or None, "limit": size})
        try:
            body = api_get(path, query, lang=lang)
        except AppleMusicNotFound:
            return [], False          # offset past the end of a playlist -> 404
        block = key(body) if key else body
        block = block or {}
        return block.get("data") or [], bool(block.get("next"))

    results = run_parallel([lambda c=c: fetch(c) for c in chunks])
    items, has_more = [], False
    for data, more in results:
        items.extend(data)
        has_more = more
        if len(data) == 0:
            has_more = False
            break
    return items, has_more


def follow_all(first_block, *, max_items, lang=None, max_per_call=100):
    """Extend a relationship/view block ({data, next}) by following `next`
    until exhausted or `max_items` collected (album tracklists > 300)."""
    items = list((first_block or {}).get("data") or [])
    nxt = (first_block or {}).get("next")
    while nxt and len(items) < max_items:
        path, _, qs = nxt.partition("?")
        params = dict(parse_qsl(qs, keep_blank_values=True))   # decoded: re-encoded on send
        params["limit"] = max_per_call
        body = api_get(path, params, lang=lang)
        items.extend(body.get("data") or [])
        nxt = body.get("next")
    return items[:max_items]


def run_parallel(fns):
    """Run zero-arg callables in parallel; results align with `fns`.
    Exceptions propagate from the first failing call."""
    if not fns:
        return []
    if len(fns) == 1:
        return [fns[0]()]
    with ThreadPoolExecutor(max_workers=min(FANOUT_WORKERS, len(fns))) as ex:
        futures = [ex.submit(fn) for fn in fns]
        return [f.result() for f in futures]


if __name__ == "__main__":
    # Smoke test: python apple_music/fetch.py [song id]
    target = sys.argv[1] if len(sys.argv) > 1 else "1440841367"
    tok = developer_token()
    print("token exp:", jwt_payload(tok).get("exp"))
    song = resource("us", "songs", target, lang="en-US")
    print(song["attributes"]["name"], "-", song["attributes"]["artistName"])
