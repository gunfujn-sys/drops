# -*- coding: utf-8 -*-
"""新着を取得して data/items.json を更新する。

取得元は2つ。
  1. ブランド公式ストア（Shopify）… 認証不要。すぐ動く。公式の新作だけが入る。
  2. 楽天市場API … RAKUTEN_APP_ID があるときだけ。アフィリエイトリンクになる。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from sources import rakuten, shopify

ROOT = lib.ROOT
DB_PATH = os.path.join(ROOT, "data", "items.json")


def load(name):
    with open(os.path.join(ROOT, "config", name), "r", encoding="utf-8") as f:
        return json.load(f)


def decorate(it, brand):
    it["brand"] = brand["id"]
    it["brand_name"] = brand["name"]
    it["scene"] = brand["scene"]
    it["title"] = lib.clean_title(it["title"], brand["name"])
    hint = it.get("genre_id", "") if it.get("source") == "shopify" else ""
    cat = lib.classify(hint) if hint else "acc"
    if not hint or cat == "acc":
        cat = lib.classify(it["title"])
    it["category"] = cat
    return it


def from_shopify(brand_by_id, only):
    conf = load("stores.json")
    now = lib.now_jst()
    out = []
    for st in conf["stores"]:
        b = brand_by_id.get(st["brand"])
        if not b or (only and b["id"] != only):
            continue
        if st.get("currency", "JPY") != "JPY":
            print("  %-16s skip（%s建て）" % (b["id"], st.get("currency")))
            continue
        got = shopify.fetch_store(st, now, conf["max_age_days"], conf["per_store"])
        for it in got:
            out.append(decorate(it, b))
        print("  %-16s %3d件  （公式）" % (b["id"], len(got)))
    return out


def from_rakuten(brands, conf, only, app_id, access_key, aff_id):
    genres = conf["rakuten_genres"]
    ng_words = conf["ng_words"]
    ng_shop = conf["ng_shop_words"]
    ng_keyword = " ".join(ng_words[:10])
    out = []
    for b in brands:
        if only and b["id"] != only:
            continue
        got = kept = 0
        for gname in b.get("genres", ["mens"]):
            gid = genres.get(gname)
            if not gid:
                continue
            raw = rakuten.search(b, gid, app_id, aff_id, ng_keyword=ng_keyword,
                                 access_key=access_key)
            got += len(raw)
            for it in raw:
                if lib.is_noise(it, b, ng_words, ng_shop):
                    continue
                out.append(decorate(it, b))
                kept += 1
        print("  %-16s %3d/%3d 件  （楽天）" % (b["id"], kept, got))
    return out


def main():
    site = load("site.json")
    conf = load("brands.json")
    brands = conf["brands"]
    brand_by_id = dict((b["id"], b) for b in brands)

    only = None
    skip_rakuten = False
    for a in sys.argv[1:]:
        if a.startswith("--brand="):
            only = a.split("=", 1)[1]
        if a == "--official-only":
            skip_rakuten = True

    collected = []

    print("[1] ブランド公式ストア")
    collected += from_shopify(brand_by_id, only)

    app_id, access_key, aff_id = rakuten.credentials()
    if skip_rakuten or not app_id or not access_key:
        missing = " と ".join([n for n, v in
                              (("RAKUTEN_APP_ID", app_id), ("RAKUTEN_ACCESS_KEY", access_key)) if not v])
        print("[2] 楽天市場API … %s が無いので省略" % (missing or "認証情報"))
        print("    （https://webservice.rakuten.co.jp/ で発行すると、対象ブランドが一気に増えます）")
    else:
        if not aff_id:
            print("! RAKUTEN_AFFILIATE_ID が未設定です。楽天のリンクは通常URLになり報酬は発生しません。",
                  file=sys.stderr)
        print("[2] 楽天市場API")
        collected += from_rakuten(brands, conf, only, app_id, access_key, aff_id)

    if not collected:
        sys.exit("1件も取得できませんでした。ネットワークか設定を確認してください。")

    collected = lib.dedupe(collected)
    print("重複除去後 %d件" % len(collected))

    db = lib.load_db(DB_PATH)
    if db.get("demo"):
        print("ダミーデータを破棄して実データに切り替えます")
        db = {"items": {}}
    added, dropped = lib.merge(db, collected, site["retention_days"], site["max_items"])
    db["updated_at"] = lib.now_jst().strftime("%Y-%m-%d %H:%M")
    db.pop("demo", None)
    lib.save_db(DB_PATH, db)
    print("新規 %d件 / 掲載終了 %d件 / 総掲載 %d件" % (added, dropped, len(db["items"])))


if __name__ == "__main__":
    main()
