# Temporary: finds the Spotify link for an Apple Music album (by its id and UPC).
import html
import json
import os
import re
import urllib.parse
import urllib.request

APPLE_ID = "6825785062"
UPC = "711641055471"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = "check-results"
os.makedirs(OUT, exist_ok=True)
res = {"pages": [], "spotify": [], "deezer": None, "errors": []}


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if raw else data.decode("utf-8", "replace")


found = []
for u in [f"https://album.link/i/{APPLE_ID}", f"https://song.link/i/{APPLE_ID}", f"https://odesli.co/i/{APPLE_ID}"]:
    try:
        page = get(u)
        ids = sorted(set(re.findall(r"open\.spotify\.com(?:\\u002F|/)album(?:\\u002F|/)([A-Za-z0-9]{22})", page)))
        res["pages"].append({"url": u, "length": len(page), "spotify_ids": ids})
        found += [i for i in ids if i not in found]
        if found:
            break
    except Exception as e:
        res["errors"].append(f"{u}: {e!r}")

try:
    d = json.loads(get(f"https://api.deezer.com/album/upc:{UPC}"))
    res["deezer"] = {k: d.get(k) for k in ["id", "title", "link", "label", "release_date", "record_type", "nb_tracks", "cover_xl", "error"]}
    if d.get("link") and not found:
        page = get("https://album.link/" + urllib.parse.quote(d["link"], safe=""))
        ids = sorted(set(re.findall(r"open\.spotify\.com(?:\\u002F|/)album(?:\\u002F|/)([A-Za-z0-9]{22})", page)))
        res["pages"].append({"url": "album.link deezer", "spotify_ids": ids})
        found += ids
except Exception as e:
    res["errors"].append(f"deezer: {e!r}")

for sid in found[:2]:
    u = f"https://open.spotify.com/album/{sid}"
    row = {"url": u}
    try:
        o = json.loads(get("https://open.spotify.com/oembed?url=" + urllib.parse.quote(u, safe="")))
        row["oembed_title"] = o.get("title")
        row["thumbnail"] = o.get("thumbnail_url")
        page = get(u)
        t = re.search(r"<title>(.*?)</title>", page, re.S)
        row["page_title"] = html.unescape(t.group(1)) if t else None
        for name in ["og:description", "music:release_date", "music:musician_description"]:
            m = re.search(r'<meta (?:property|name)="' + re.escape(name) + r'" content="([^"]*)"', page)
            row[name] = html.unescape(m.group(1)) if m else None
        if row.get("thumbnail"):
            data = get(row["thumbnail"].replace("ab67616d00001e02", "ab67616d0000b273"), raw=True)
            with open(f"{OUT}/cover-spotify.jpg", "wb") as f:
                f.write(data)
            row["cover_bytes"] = len(data)
    except Exception as e:
        row["error"] = repr(e)
    res["spotify"].append(row)

with open(f"{OUT}/lookup2.json", "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
