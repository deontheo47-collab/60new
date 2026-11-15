"""Collects Botswana news headlines from RSS feeds into news.json (standard library only)."""
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

FEEDS = [
    ("The Voice", "https://thevoicebw.com/feed"),
    ("Sunday Standard", "https://sundaystandard.info/feed"),
    ("Botswana Guardian", "https://guardiansun.co.bw/rssFeed/48"),
    ("Botswana Unplugged", "https://botswanaunplugged.com/feed"),
]

# Rough keyword matching. Anything that does not match is filed under "Other".
TOPICS = {
    "Politics": ["parliament", "minister", "president", "government", "election", "cabinet", "court", "bdp", "udc", "opposition", "policy"],
    "Business": ["bank", "economy", "business", "company", "mining", "diamond", "pula", "investment", "market", "tender", "prices"],
    "Sport": ["football", "soccer", "sport", "match", "athlet", "league", "olympic", "coach", "tournament"],
    "Entertainment": ["music", "artist", "album", "movie", "film", "actor", "celebrity", "concert", "rapper", "entertainment", "musician"],
    "Education": ["school", "university", "student", "exam", "education", "teacher", "graduat", "learner"],
}


def classify(text):
    text = text.lower()
    for topic, words in TOPICS.items():
        if any(w in text for w in words):
            return topic
    return "Other"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def clean(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def short(s, n=200):
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0] + "…"


def parse_date(s):
    now = datetime.now(timezone.utc)
    if not s:
        return now
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return now
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse(data, source):
    root = ET.fromstring(data)
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f, cats = {}, []
        for c in el:
            k = local(c.tag)
            if k == "category":
                cats.append(c.attrib.get("term") or c.text or "")
            elif k == "link":
                f.setdefault("link", (c.attrib.get("href") or c.text or "").strip())
            elif k in ("title", "description", "summary", "pubDate", "published", "updated"):
                f.setdefault(k, c.text or "")
        title = clean(f.get("title"))
        link = f.get("link", "")
        if not title or not link.startswith("http"):
            continue
        items.append({
            "source": source,
            "title": title,
            "link": link,
            "summary": short(clean(f.get("description") or f.get("summary"))),
            "published": parse_date(f.get("pubDate") or f.get("published") or f.get("updated")),
            "topic": classify(title + " " + " ".join(cats)),
        })
    return items


def main():
    items, seen = [], set()
    for source, url in FEEDS:
        try:
            req = Request(url, headers={"User-Agent": "60new-collector/1.0"})
            with urlopen(req, timeout=20) as r:
                got = parse(r.read(), source)
            print(source, len(got), "items")
            for it in sorted(got, key=lambda x: x["published"], reverse=True)[:15]:
                if it["link"] not in seen:
                    seen.add(it["link"])
                    items.append(it)
        except Exception as e:
            print("FAILED", source, e, file=sys.stderr)
    if not items:
        print("No headlines collected, keeping the old file.", file=sys.stderr)
        sys.exit(1)
    items.sort(key=lambda x: x["published"], reverse=True)
    for it in items:
        it["published"] = it["published"].isoformat()
    out = {"updated": datetime.now(timezone.utc).isoformat(), "items": items[:60]}
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("Saved", len(out["items"]), "headlines")


if __name__ == "__main__":
    main()
