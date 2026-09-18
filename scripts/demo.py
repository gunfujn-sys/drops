# -*- coding: utf-8 -*-
"""APIキー無しで見た目を確認するためのダミーデータ生成。"""
import json
import os
import random
import sys
import urllib.parse
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

ROOT = lib.ROOT
random.seed(7)

NOUNS = {
    "outer": ["Nylon Coach Jacket", "Down Puffer Vest", "Wool Chesterfield Coat", "Mods Coat"],
    "sweat": ["Box Logo Hooded Sweatshirt", "Arc Crewneck", "Zip Up Hoodie"],
    "knit": ["Mohair Cardigan", "Cable Knit Sweater", "Rib Knit Polo"],
    "shirt": ["Open Collar Shirt", "Flannel Check Shirt", "Oxford B.D Shirt"],
    "tee": ["Small Logo Tee", "Graphic S/S Tee", "Pocket L/S Tee"],
    "pants": ["Wide Denim Pants", "Track Pants", "Chino Trousers", "Cargo Pants"],
    "shoes": ["990v6", "Air Force 1 Low", "GEL-KAYANO 14", "XT-6 Expanse"],
    "bag": ["Shoulder Bag", "Backpack 26L", "Leather Wallet"],
    "cap": ["6 Panel Cap", "Corduroy Bucket Hat", "Logo Beanie"],
    "acc": ["Logo Socks 3pack", "Leather Belt", "Silver Ring"],
}
SHOPS = ["SELECT STORE TOKYO", "AVENUE STORE", "essence", "ARKnets", "1-ST", "ROOM ONLINE"]
TONES = ["#dfdcd6", "#cfd6db", "#e3dbd2", "#d8d8d8", "#d5dbd2", "#e6dcdc"]


def ph(text, tone):
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 400'>"
           "<rect width='400' height='400' fill='%s'/>"
           "<rect x='110' y='96' width='180' height='210' rx='6' fill='rgba(255,255,255,.55)'/>"
           "<text x='200' y='212' font-family='Helvetica' font-size='17' fill='#6a6a6a' "
           "text-anchor='middle'>%s</text></svg>") % (tone, text)
    return "data:image/svg+xml," + urllib.parse.quote(svg)


def main():
    conf = json.load(open(os.path.join(ROOT, "config", "brands.json"), encoding="utf-8"))
    items = {}
    for b in conf["brands"]:
        for n in range(random.randint(5, 11)):
            cat = random.choice(list(NOUNS.keys()))
            if b["scene"] == "sneaker":
                cat = "shoes" if random.random() < .85 else "acc"
            title = "%s %s" % (b["name"], random.choice(NOUNS[cat]))
            price = int(b.get("min_price", 5000) * random.uniform(1.0, 3.4) // 100 * 100)
            days = random.choice([0, 0, 1, 2, 3, 5, 6, 8, 12, 17])
            key = "demo:%s-%d" % (b["id"], n)
            items[key] = {
                "id": key, "source": "demo", "title": title, "price": price,
                "url": "https://example.com/" + b["id"], "raw_url": "",
                "image": ph(b["name"], random.choice(TONES)),
                "shop": random.choice(SHOPS), "shop_code": "demo",
                "genre_id": "0", "reviews": random.randint(0, 40), "rating": 0,
                "affiliate_rate": 3.0, "brand": b["id"], "brand_name": b["name"],
                "scene": b["scene"], "category": cat,
                "first_seen": (lib.now_jst() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "last_seen": lib.today(),
            }
    db = {"items": items, "updated_at": lib.now_jst().strftime("%Y-%m-%d %H:%M"), "demo": True}
    lib.save_db(os.path.join(ROOT, "data", "items.json"), db)
    print("ダミー %d件を data/items.json に書きました（本番実行で上書きされます）" % len(items))


if __name__ == "__main__":
    main()
