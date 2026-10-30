import json, re, os, unicodedata, urllib.request, urllib.parse, time
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r: return json.loads(r.read().decode("utf-8", "replace"))
def n(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", (s or "").replace("ı", "i").replace("İ", "I")).encode("ascii", "ignore").decode().lower())
def close(a, b): a, b = n(a), n(b); return bool(a) and bool(b) and (a == b or a in b or b in a)
os.makedirs("check-results", exist_ok=True); out = []
for it in json.load(open(".github/claude/label-todo.json")):
    rec = dict(it)
    try:
        clean = re.sub(r"open\.spotify\.com/intl-[a-z]+/", "open.spotify.com/", it["url"])
        rec["spotify_title"] = get("https://open.spotify.com/oembed?url=" + urllib.parse.quote(clean, safe="")).get("title")
    except Exception as e: rec["spotify_title"] = f"ERR {e}"[:80]
    title = rec["spotify_title"] if rec["spotify_title"] and not rec["spotify_title"].startswith("ERR") else it["title"]
    artist_main = re.split(r"\s*&\s*", it["artist"])[0]
    # Deezer
    try:
        q = urllib.parse.quote(f'artist:"{artist_main}" album:"{title}"')
        hits = get(f"https://api.deezer.com/search/album?q={q}").get("data", [])
        if not hits: hits = get("https://api.deezer.com/search/album?q=" + urllib.parse.quote(f"{artist_main} {title}")).get("data", [])
        hit = next((h for h in hits if close(h["title"], title) and close(h["artist"]["name"], artist_main)), None)
        if hit:
            alb = get(f"https://api.deezer.com/album/{hit['id']}")
            rec["deezer"] = {"title": alb.get("title"), "artist": alb.get("artist", {}).get("name"), "label": alb.get("label"), "date": alb.get("release_date"), "type": alb.get("record_type")}
        else: rec["deezer"] = {"none": [(h["title"], h["artist"]["name"]) for h in hits[:3]]}
    except Exception as e: rec["deezer"] = {"error": str(e)[:80]}
    # Apple Music / iTunes
    rec["itunes"] = None
    for country in ("tr", "us"):
        try:
            res = get("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": f"{artist_main} {title}", "entity": "album", "limit": 10, "country": country})).get("results", [])
            hit = next((r for r in res if close(r.get("collectionName", "").replace(" - Single", "").replace(" - EP", ""), title) and close(r.get("artistName"), artist_main)), None)
            if hit:
                rec["itunes"] = {"store": country, "title": hit.get("collectionName"), "artist": hit.get("artistName"), "copyright": hit.get("copyright"), "date": (hit.get("releaseDate") or "")[:10]}; break
        except Exception as e: rec["itunes"] = {"error": str(e)[:80]}
        time.sleep(1)
    out.append(rec); print(json.dumps(rec, ensure_ascii=False))
    time.sleep(0.5)
json.dump(out, open("check-results/labels.json", "w"), ensure_ascii=False, indent=1)
