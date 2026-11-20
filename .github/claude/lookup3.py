# Temporary: release details and cover for a Spotify track.
import html
import json
import os
import re
import urllib.parse
import urllib.request

TRACK = "https://open.spotify.com/track/3MdYTWMk04Nz6aHW6zeaQo"
ARTIST = "Emir Aksoy"
TITLE = "Bin Yıllık Dert"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = "check-results"
os.makedirs(OUT, exist_ok=True)
res = {"spotify": {}, "itunes": [], "deezer": [], "errors": []}


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if raw else data.decode("utf-8", "replace")


def norm(s):
    return re.sub(r"\W", "", (s or "").lower())


try:
    o = json.loads(get("https://open.spotify.com/oembed?url=" + urllib.parse.quote(TRACK, safe="")))
    res["spotify"]["oembed_title"] = o.get("title")
    res["spotify"]["thumbnail"] = o.get("thumbnail_url")
    page = get(TRACK)
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    res["spotify"]["page_title"] = html.unescape(t.group(1)) if t else None
    for name in ["og:description", "og:title", "music:release_date", "music:album", "music:musician_description"]:
        m = re.search(r'<meta (?:property|name)="' + re.escape(name) + r'" content="([^"]*)"', page)
        res["spotify"][name] = html.unescape(m.group(1)) if m else None
    if res["spotify"].get("thumbnail"):
        data = get(res["spotify"]["thumbnail"].replace("ab67616d00001e02", "ab67616d0000b273"), raw=True)
        with open(f"{OUT}/cover-spotify.jpg", "wb") as f:
            f.write(data)
        res["spotify"]["cover_bytes"] = len(data)
except Exception as e:
    res["errors"].append(f"spotify: {e!r}")

try:
    for country in ["TR", "US"]:
        q = urllib.parse.urlencode({"term": f"{ARTIST} {TITLE}", "entity": "song", "limit": 25, "country": country})
        for a in json.loads(get("https://itunes.apple.com/search?" + q)).get("results", []):
            if norm(ARTIST) in norm(a.get("artistName")):
                res["itunes"].append({k: a.get(k) for k in ["trackName", "collectionName", "artistName", "releaseDate", "collectionId", "trackViewUrl"]} | {"country": country})
    for cid in sorted({r["collectionId"] for r in res["itunes"] if r.get("collectionId")})[:3]:
        d = json.loads(get(f"https://itunes.apple.com/lookup?id={cid}&country=TR")).get("results", [])
        if d:
            res["itunes"].append({"lookup": cid, "copyright": d[0].get("copyright"), "releaseDate": d[0].get("releaseDate"), "collectionName": d[0].get("collectionName")})
except Exception as e:
    res["errors"].append(f"itunes: {e!r}")

try:
    q = urllib.parse.quote(f'artist:"{ARTIST}" track:"{TITLE}"')
    for t in json.loads(get("https://api.deezer.com/search?q=" + q)).get("data", [])[:5]:
        alb = json.loads(get(f"https://api.deezer.com/album/{t['album']['id']}"))
        res["deezer"].append({"title": t.get("title"), "album": alb.get("title"), "label": alb.get("label"), "release_date": alb.get("release_date"), "record_type": alb.get("record_type")})
except Exception as e:
    res["errors"].append(f"deezer: {e!r}")

with open(f"{OUT}/lookup3.json", "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
