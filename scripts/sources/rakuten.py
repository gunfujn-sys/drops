# -*- coding: utf-8 -*-
"""楽天市場 商品検索API アダプタ。標準ライブラリのみ。"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
UA = "drops-newarrivals/1.0 (+github actions)"
SLEEP = 1.2  # 楽天は1秒1リクエストが目安

name = "rakuten"


def _get(params, retries=4):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code == 429 or e.code >= 500:
                wait = SLEEP * (2 ** (attempt + 1))
                print("    retry %ss (HTTP %s)" % (round(wait, 1), e.code), file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 400:
                if "applicationId" in body or "accessKey" in body or "access key" in body.lower():
                    raise RuntimeError(
                        "楽天APIに拒否されました（アプリIDを確認してください）: %s" % body)
                # パラメータ起因の400は、そのリクエストだけ諦めて先に進む
                print("    skip (400): %s" % body, file=sys.stderr)
                return None
            raise RuntimeError("楽天API HTTP %s: %s" % (e.code, body))
        except urllib.error.URLError as e:
            time.sleep(SLEEP * (attempt + 1))
            last = e
    print("    give up after %d retries" % retries, file=sys.stderr)
    return None


def big_image(url):
    """128x128のサムネURLを大きい画像に差し替える。"""
    if not url:
        return ""
    url = url.split("?")[0]
    return url + "?_ex=600x600"


def search(brand, genre_id, app_id, affiliate_id, ng_keyword="", pages=2, access_key=""):
    """1ブランド×1ジャンルぶんの生アイテムを返す。"""
    out = []
    for page in range(1, pages + 1):
        params = {
            "applicationId": app_id,
            "format": "json",
            "formatVersion": 2,
            "keyword": brand["keyword"],
            "genreId": genre_id,
            "hits": 30,
            "page": page,
            "sort": "-updateTimestamp",
            "imageFlag": 1,
            "availability": 1,
            "minPrice": brand.get("min_price", 3000),
        }
        if access_key:
            params["accessKey"] = access_key
        if affiliate_id:
            params["affiliateId"] = affiliate_id
        if ng_keyword:
            params["NGKeyword"] = ng_keyword
        time.sleep(SLEEP)
        data = _get(params)
        if not data and ng_keyword:
            # NGKeywordが受け付けられない場合があるので外して一度だけ再試行
            params.pop("NGKeyword", None)
            time.sleep(SLEEP)
            data = _get(params)
        if not data:
            break
        items = data.get("Items") or []
        for it in items:
            imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
            first = imgs[0] if imgs else ""
            if isinstance(first, dict):
                first = first.get("imageUrl", "")
            out.append({
                "id": "rakuten:" + it.get("itemCode", ""),
                "source": "rakuten",
                "title": it.get("itemName", ""),
                "price": it.get("itemPrice", 0),
                "url": it.get("affiliateUrl") or it.get("itemUrl", ""),
                "raw_url": it.get("itemUrl", ""),
                "image": big_image(first),
                "shop": it.get("shopName", ""),
                "shop_code": it.get("shopCode", ""),
                "genre_id": str(it.get("genreId", "")),
                "reviews": it.get("reviewCount", 0),
                "rating": it.get("reviewAverage", 0),
                "affiliate_rate": it.get("affiliateRate", 0),
            })
        if len(items) < 30:
            break
    return out


def credentials():
    """新仕様では applicationId と accessKey の両方が要る。"""
    app_id = os.environ.get("RAKUTEN_APP_ID", "").strip()
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()
    aff_id = os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip()
    return app_id, access_key, aff_id
