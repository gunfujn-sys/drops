# -*- coding: utf-8 -*-
"""ブランド公式ストア（Shopify）の公開商品一覧から新着を取得する。認証不要。

/products.json は公開エンドポイントで、published_at の新しい順に返る。
本文や画像を複製せず、商品名・価格・公式ページへのリンク・画像URLだけを使う。
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
SLEEP = 1.0
MAX_PAGES = 3

name = "shopify"


def _get(url, retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "ja,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 430) or e.code >= 500:
                time.sleep(SLEEP * (2 ** (attempt + 1)))
                continue
            print("    HTTP %s %s" % (e.code, url), file=sys.stderr)
            return None
        except (urllib.error.URLError, ValueError) as e:
            print("    取得失敗 %s (%s)" % (url, e), file=sys.stderr)
            time.sleep(SLEEP * (attempt + 1))
    return None


def big_image(src, px=800):
    if not src:
        return ""
    sep = "&" if "?" in src else "?"
    return "%s%swidth=%d" % (src, sep, px)


def price_of(product):
    prices = []
    for v in product.get("variants", []):
        try:
            prices.append(int(float(v.get("price") or 0)))
        except (TypeError, ValueError):
            continue
    return min(prices) if prices else 0


def in_stock(product):
    return any(v.get("available") for v in product.get("variants", []))


def fetch_store(store, now, max_age_days, per_store):
    """1ストア分の新着を返す。"""
    domain = store["domain"].rstrip("/")
    host = urllib.parse.urlparse(domain).netloc
    limit_date = (now - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    # 期間で切る。件数で切ると、再公開の多い店で窓がずれて同じ商品が「新規」に混ざる。
    products = []
    for page in range(1, MAX_PAGES + 1):
        time.sleep(SLEEP)
        # country=JP を必ず付ける。付けないとアクセス元の国で通貨が変わり、
        # 米国のGitHub Actionsから叩いたときにドル価格が返ってくる。
        data = _get("%s/products.json?limit=250&page=%d&country=%s"
                    % (domain, page, store.get("country", "JP")))
        if not data or not data.get("products"):
            break
        chunk = data["products"]
        products += chunk
        oldest = min((p.get("published_at") or "")[:10] for p in chunk)
        if len(chunk) < 250 or oldest < limit_date:
            break
    if not products:
        return []

    vendors = [v.lower() for v in store.get("vendor_match", [])]
    out = []
    for p in products:
        if vendors:
            v = (p.get("vendor") or "").lower()
            if not any(t in v for t in vendors):
                continue
        pub = (p.get("published_at") or p.get("created_at") or "")[:10]
        if pub and pub < limit_date:
            continue
        if not in_stock(p):
            continue
        price = price_of(p)
        if price <= 0:
            continue
        images = p.get("images") or []
        src = images[0].get("src", "") if images else ""
        if not src:
            continue
        src2 = images[1].get("src", "") if len(images) > 1 else ""
        out.append({
            "id": "shopify:%s:%s" % (host, p.get("id")),
            "source": "shopify",
            "title": (p.get("title") or "").strip(),
            "price": price,
            "url": "%s/products/%s" % (domain, p.get("handle", "")),
            "raw_url": "%s/products/%s" % (domain, p.get("handle", "")),
            "image": big_image(src),
            "image2": big_image(src2) if src2 else "",
            "shop": store.get("shop", host),
            "shop_code": host,
            "genre_id": (p.get("product_type") or "").strip(),
            "reviews": 0,
            "rating": 0,
            "affiliate_rate": 0,
            "first_seen_hint": pub or None,
        })
    # 並びを毎回同じにする（同じ日付の中は商品IDの新しい順）
    out.sort(key=lambda x: ((x.get("first_seen_hint") or ""), x["id"]), reverse=True)
    return out[:per_store]
