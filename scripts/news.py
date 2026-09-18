# -*- coding: utf-8 -*-
"""掲載ブランドに関係するニュースの見出しをRSSから集める。"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

ROOT = lib.ROOT
NEWS_PATH = os.path.join(ROOT, "data", "news.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) drops-newsbot/1.0"


def load(name):
    with open(os.path.join(ROOT, "config", name), "r", encoding="utf-8") as f:
        return json.load(f)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as res:
        return res.read()


def parse_feed(blob):
    root = ET.fromstring(blob)
    items = root.findall("./channel/item")
    if not items:  # Atom
        ns = "{http://www.w3.org/2005/Atom}"
        for e in root.findall(ns + "entry"):
            link = e.find(ns + "link")
            items.append(e)
    out = []
    for it in items:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        date = (it.findtext("pubDate") or it.findtext("updated") or "").strip()
        if not title or not link:
            continue
        try:
            dt = parsedate_to_datetime(date).astimezone(lib.JST)
        except Exception:
            dt = lib.now_jst()
        out.append({"title": re.sub(r"\s+", " ", title), "url": link,
                    "date": dt.strftime("%Y-%m-%d")})
    return out


def matcher(brands):
    """ブランドごとの照合パターン。英字は前後が英数字でない場合だけ一致させる。"""
    pats = {}
    for b in brands:
        if b.get("news_match"):
            terms = set(b["news_match"])
        else:
            terms = set(b.get("match", [])) | set([b["name"]])
        regs = []
        for t in terms:
            t = lib.normalize(t).strip()
            # 2文字以下は誤爆する（「オン」が「ディオン」に当たる等）
            if len(t) < 3:
                continue
            if re.match(r"^[0-9a-z\-\. ]+$", t):
                regs.append(re.compile(r"(?<![0-9a-z])" + re.escape(t) + r"(?![0-9a-z])"))
            else:
                regs.append(re.compile(re.escape(t)))
        pats[b["id"]] = (b["name"], regs)
    return pats


def main():
    conf = load("news.json")
    brands = load("brands.json")["brands"]
    pats = matcher(brands)

    found = []
    for feed in conf["feeds"]:
        try:
            entries = parse_feed(fetch(feed["url"]))
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError) as e:
            print("  ! %s 取得失敗: %s" % (feed["name"], e), file=sys.stderr)
            continue
        hit = 0
        for e in entries:
            t = lib.normalize(e["title"])
            tags = [bid for bid, (nm, regs) in pats.items() if any(r.search(t) for r in regs)]
            if not tags:
                continue
            e["source"] = feed["name"]
            e["brands"] = tags
            e["id"] = e["url"]
            found.append(e)
            hit += 1
        print("  %-12s %3d/%3d 件がブランド該当" % (feed["name"], hit, len(entries)))

    db = lib.load_db(NEWS_PATH)
    items = db.setdefault("items", {})
    added = 0
    for e in found:
        if e["id"] not in items:
            added += 1
        e["first_seen"] = items.get(e["id"], {}).get("first_seen", lib.today())
        items[e["id"]] = e

    limit = (lib.now_jst() - timedelta(days=conf["keep_days"])).strftime("%Y-%m-%d")
    for k in [k for k, v in items.items() if v.get("date", "") < limit]:
        del items[k]
    if len(items) > conf["max_items"]:
        keep = sorted(items.values(), key=lambda x: x.get("date", ""), reverse=True)[:conf["max_items"]]
        ids = set(x["id"] for x in keep)
        for k in list(items):
            if k not in ids:
                del items[k]

    db["updated_at"] = lib.now_jst().strftime("%Y-%m-%d %H:%M")
    lib.save_db(NEWS_PATH, db)
    print("ニュース 新規%d件 / 保持%d件" % (added, len(items)))


if __name__ == "__main__":
    main()
