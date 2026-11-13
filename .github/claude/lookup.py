# Temporary: finds a release (link, type, year, label, cover) on public music services.
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

ARTIST = "ototoi"
TITLE = "Fluid Obsessions"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = "check-results"
os.makedirs(OUT, exist_ok=True)
res = {"deezer": [], "itunes": [], "bandcamp": [], "odesli": [], "spotify": [], "musicbrainz": [], "web": [], "covers": [], "errors": []}


def get(url, raw=False, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}
    if headers:
        h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read()
    return data if raw else data.decode("utf-8", "replace")


def jget(url, **kw):
    return json.loads(get(url, **kw))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_artist(s):
    return norm(ARTIST) in norm(s)


def is_title(s):
    return norm(TITLE)[:12] in norm(s)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def step(name, fn):
    try:
        fn()
    except Exception as e:  # keep going with the other sources
        res["errors"].append(f"{name}: {e!r}")


def deezer():
    seen = set()
    for q in [f'artist:"{ARTIST}" album:"{TITLE}"', f"{ARTIST} {TITLE}", TITLE]:
        d = jget("https://api.deezer.com/search/album?limit=50&q=" + urllib.parse.quote(q))
        for a in d.get("data", []):
            if a["id"] in seen or not (is_artist(a.get("artist", {}).get("name")) or is_title(a.get("title"))):
                continue
            seen.add(a["id"])
            full = jget(f"https://api.deezer.com/album/{a['id']}")
            row = {k: full.get(k) for k in ["id", "title", "link", "label", "release_date", "record_type", "nb_tracks", "cover_xl", "upc"]}
            row["artist"] = full.get("artist", {}).get("name")
            res["deezer"].append(row)
        time.sleep(0.5)
    d = jget("https://api.deezer.com/search/artist?q=" + urllib.parse.quote(ARTIST))
    for ar in d.get("data", [])[:5]:
        if not is_artist(ar.get("name")):
            continue
        for a in jget(f"https://api.deezer.com/artist/{ar['id']}/albums?limit=100").get("data", []):
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            res["deezer"].append({"id": a["id"], "title": a.get("title"), "link": a.get("link"), "release_date": a.get("release_date"),
                                  "record_type": a.get("record_type"), "cover_xl": a.get("cover_xl"), "artist": ar.get("name"), "from_artist_list": True})


def itunes():
    seen = set()
    for term in [f"{ARTIST} {TITLE}", ARTIST, TITLE]:
        for country in ["TR", "US"]:
            q = urllib.parse.urlencode({"term": term, "entity": "album", "limit": 50, "country": country})
            for a in jget("https://itunes.apple.com/search?" + q).get("results", []):
                if a.get("collectionId") in seen or not (is_artist(a.get("artistName")) or is_title(a.get("collectionName"))):
                    continue
                seen.add(a.get("collectionId"))
                row = {k: a.get(k) for k in ["collectionId", "collectionName", "artistName", "releaseDate", "copyright", "trackCount", "collectionViewUrl", "artworkUrl100"]}
                row["country"] = country
                res["itunes"].append(row)
            time.sleep(1)


def bandcamp():
    for i, q in enumerate([f"{ARTIST} {TITLE}", ARTIST]):
        page = get("https://bandcamp.com/search?" + urllib.parse.urlencode({"q": q}))
        found = 0
        for m in re.finditer(r'<li class="searchresult(.*?)</li>', page, re.S):
            b = m.group(1)

            def pick(pat):
                x = re.search(pat, b, re.S)
                return clean(x.group(1)) if x else None

            img = re.search(r'<img src="([^"]+)"', b)
            res["bandcamp"].append({"query": q, "type": pick(r'<div class="itemtype">(.*?)</div>'), "heading": pick(r'<div class="heading">(.*?)</div>'),
                                    "subhead": pick(r'<div class="subhead">(.*?)</div>'), "released": pick(r'<div class="released">(.*?)</div>'),
                                    "url": pick(r'<div class="itemurl">(.*?)</div>'), "img": img.group(1) if img else None})
            found += 1
        if not found:
            with open(f"{OUT}/bandcamp-search-{i}.txt", "w") as f:
                f.write(clean(page)[:4000])
        time.sleep(1)


def bandcamp_pages():
    for row in list(res["bandcamp"]):
        url = (row.get("url") or "").split("?")[0]
        if not url.startswith("http") or not (is_title(row.get("heading")) or row.get("type") in ("ALBUM", "TRACK") and is_artist(row.get("subhead"))):
            continue
        page = get(url)
        meta = {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', page)}
        rel = re.search(r'(released|releases) ([A-Z][a-z]+ \d{1,2}, \d{4})', page)
        row["page"] = {"title": meta.get("og:title"), "image": meta.get("og:image"), "description": (meta.get("description") or "")[:400],
                       "released": rel.group(0) if rel else None}
        time.sleep(1)


def odesli():
    urls = [r["link"] for r in res["deezer"] if is_title(r.get("title")) and r.get("link")]
    urls += [r["collectionViewUrl"] for r in res["itunes"] if is_title(r.get("collectionName")) and r.get("collectionViewUrl")]
    urls += [r["url"] for r in res["bandcamp"] if is_title(r.get("heading")) and (r.get("url") or "").startswith("http")]
    for u in urls[:4]:
        try:
            d = jget("https://api.song.link/v1-alpha.1/links?" + urllib.parse.urlencode({"url": u, "userCountry": "TR"}))
            links = {k: v.get("url") for k, v in d.get("linksByPlatform", {}).items()}
            res["odesli"].append({"from": u, "links": links})
            if links.get("spotify"):
                return
        except Exception as e:
            res["errors"].append(f"odesli {u}: {e!r}")
        time.sleep(2)


def web():
    q = f'"{ARTIST}" "{TITLE}"'
    page = get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q}))
    for m in re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        href = html.unescape(m.group(1))
        u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
        res["web"].append({"url": u, "title": clean(m.group(2))})


def spotify():
    urls = [o["links"]["spotify"] for o in res["odesli"] if o["links"].get("spotify")]
    urls += [w["url"] for w in res["web"] if "open.spotify.com/" in w["url"] and ("/album/" in w["url"] or "/track/" in w["url"])]
    for u in urls[:3]:
        u = u.split("?")[0]
        row = {"url": u}
        o = jget("https://open.spotify.com/oembed?url=" + urllib.parse.quote(u, safe=""))
        row["oembed_title"] = o.get("title")
        row["thumbnail"] = o.get("thumbnail_url")
        try:
            page = get(u)
            t = re.search(r"<title>(.*?)</title>", page, re.S)
            row["page_title"] = clean(t.group(1)) if t else None
            for name in ["og:description", "music:release_date", "og:title"]:
                m = re.search(r'<meta (?:property|name)="' + re.escape(name) + r'" content="([^"]*)"', page)
                row[name] = html.unescape(m.group(1)) if m else None
        except Exception as e:
            row["page_error"] = repr(e)
        res["spotify"].append(row)
        time.sleep(1)


def musicbrainz():
    q = urllib.parse.urlencode({"query": f'artist:"{ARTIST}"', "fmt": "json", "limit": 50})
    d = jget("https://musicbrainz.org/ws/2/release/?" + q, headers={"User-Agent": "site-lookup/1.0 ( https://github.com/cemalbarkinengin/barkinengin.com )"})
    for r in d.get("releases", []):
        res["musicbrainz"].append({"title": r.get("title"), "date": r.get("date"), "artist": " ".join(a.get("name", "") for a in r.get("artist-credit", [])),
                                   "label": [li.get("label", {}).get("name") for li in r.get("label-info", []) or []],
                                   "type": (r.get("release-group") or {}).get("primary-type"), "id": r.get("id")})


def covers():
    cands = []
    for s in res["spotify"]:
        if s.get("thumbnail"):
            cands.append(("spotify", s["thumbnail"].replace("ab67616d00001e02", "ab67616d0000b273")))
    for r in res["deezer"]:
        if is_title(r.get("title")) and r.get("cover_xl"):
            cands.append(("deezer", r["cover_xl"]))
    for r in res["itunes"]:
        if is_title(r.get("collectionName")) and r.get("artworkUrl100"):
            cands.append(("itunes", r["artworkUrl100"].replace("100x100bb", "1000x1000bb")))
    for r in res["bandcamp"]:
        img = (r.get("page") or {}).get("image") or r.get("img")
        if is_title(r.get("heading")) and img:
            cands.append(("bandcamp", re.sub(r"_\d+\.jpg", "_10.jpg", img)))
    done = set()
    for src, u in cands:
        if src in done:
            continue
        try:
            data = get(u, raw=True)
            path = f"{OUT}/cover-{src}.jpg"
            with open(path, "wb") as f:
                f.write(data)
            res["covers"].append({"source": src, "url": u, "file": path, "bytes": len(data)})
            done.add(src)
        except Exception as e:
            res["errors"].append(f"cover {src}: {e!r}")


step("deezer", deezer)
step("itunes", itunes)
step("bandcamp", bandcamp)
step("bandcamp pages", bandcamp_pages)
step("web", web)
step("odesli", odesli)
step("spotify", spotify)
step("musicbrainz", musicbrainz)
step("covers", covers)

with open(f"{OUT}/lookup.json", "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps({k: len(v) for k, v in res.items()}))
