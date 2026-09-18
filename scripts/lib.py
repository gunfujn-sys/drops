# -*- coding: utf-8 -*-
"""共通処理：正規化・カテゴリ判定・ノイズ除去・蓄積DB。"""
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = timezone(timedelta(hours=9))

CATEGORIES = [
    ("outer", "アウター", ["ジャケット", "コート", "ブルゾン", "ダウン", "パーカ ジャケット", "アノラック",
                           "jacket", "jkt", "coat", "blouson", "parka", "vest", "ベスト", "ma-1", "n-3b"]),
    ("sweat", "スウェット", ["スウェット", "スエット", "パーカー", "フーディ", "クルーネック",
                             "sweat", "hoodie", "hooded", "crewneck", "crew neck", "crew top"]),
    ("knit", "ニット", ["ニット", "セーター", "カーディガン", "knit", "cardigan", "sweater", "モヘア"]),
    ("shirt", "シャツ", ["シャツ", "ブラウス", "shirt", "blouse"]),
    ("tee", "Tシャツ", ["tシャツ", "ｔシャツ", "カットソー", "ロンt", "t-shirt", "tee", "long sleeve"]),
    ("pants", "パンツ", ["パンツ", "デニム", "ジーンズ", "スラックス", "ショーツ", "ショートパンツ", "スカート",
                          "pants", "pant", "denim", "jeans", "trouser", "shorts", "short", "skirt"]),
    ("shoes", "シューズ", ["スニーカー", "シューズ", "ブーツ", "サンダル", "ローファー",
                           "sneaker", "shoes", "boots", "sandal", "trainer"]),
    ("bag", "バッグ", ["バッグ", "リュック", "ポーチ", "財布", "ウォレット", "トート", "ショルダー",
                       "bag", "backpack", "wallet", "tote", "pouch", "shoulder"]),
    ("cap", "キャップ・帽子", ["キャップ", "ハット", "ビーニー", "ニット帽", "cap", "hat", "beanie", "bucket"]),
    ("acc", "アクセサリー・小物", ["ソックス", "靴下", "ベルト", "マフラー", "グローブ", "ネックレス", "リング",
                                   "socks", "belt", "scarf", "glove", "necklace", "ring", "keychain"]),
]


def now_jst():
    return datetime.now(JST)


def today():
    return now_jst().strftime("%Y-%m-%d")


def normalize(s):
    """全角英数→半角、小文字化、記号と空白を潰す。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = re.sub(r"[\s　]+", " ", s)
    return s


def squash(s):
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]", "", normalize(s))


def classify(title):
    t = normalize(title)
    for cid, label, words in CATEGORIES:
        for w in words:
            if w in t:
                return cid
    return "acc"


PRODUCT_TYPE_MAP = {
    "outerwear": "outer", "jackets": "outer", "jacket": "outer", "blousons & jackets": "outer",
    "coats": "outer", "outer": "outer", "blouson": "outer",
    "fleece": "sweat", "sweatshirts": "sweat", "hoodies": "sweat", "sweat": "sweat",
    "sweaters": "knit", "knit": "knit", "knit/jersey": "knit", "knit / cut sewn": "knit",
    "knitwear": "knit",
    "shirts": "shirt", "wovens": "shirt", "shirt": "shirt", "blouses": "shirt",
    "t-shirts": "tee", "tee / knit / cut sewn": "tee", "tees": "tee", "cut sewn": "tee",
    "bottoms": "pants", "pants": "pants", "trousers": "pants", "denim": "pants",
    "skirts": "pants", "shorts": "pants",
    "shoes": "shoes", "footwear": "shoes", "sneakers": "shoes", "boots": "shoes",
    "bags": "bag", "bag": "bag", "luggage": "bag",
    "headwear": "cap", "hats": "cap", "caps": "cap",
    "accessories": "acc", "accessory": "acc", "socks": "acc", "eyewear": "acc",
}


def classify_shopify(product_type, title):
    """product_type を優先し、曖昧なら商品名で判定する。"""
    pt = normalize(product_type).strip()
    hit = PRODUCT_TYPE_MAP.get(pt)
    if hit:
        return hit
    by_title = classify(title)
    if by_title != "acc":
        return by_title
    if pt:
        return classify(pt)
    return "acc"


def category_label(cid):
    for c, label, _ in CATEGORIES:
        if c == cid:
            return label
    return "その他"


SIZE_TAIL = re.compile(
    r"(?:[\s\-–/(\[]+)(?:size\s*)?(?:xxs|xs|s|m|l|xl|xxl|2xl|3xl|free|ワンサイズ)"
    r"\s*[)\]]?\s*$", re.I)
SKU_HEAD = re.compile(r"^[0-9A-Z]{2,}[0-9A-Z]*-[0-9A-Z\-]{3,}\s+")


def clean_title(title, brand_name):
    """店舗が付ける定型の飾りを削る。"""
    t = title
    # kolor等の「26WBM-C02142-69 Coat」のような先頭品番
    t = SKU_HEAD.sub("", t)
    # 「... - ECRU - S」「... JKT M」のような末尾のサイズ表記（色違い・サイズ違いを寄せるため）
    for _ in range(2):
        t2 = SIZE_TAIL.sub("", t)
        if t2 == t or len(t2) < 3:
            break
        t = t2
    t = re.sub(r"[【\[(（][^】\])）]{0,24}(送料無料|あす楽|ポイント|クーポン|SALE|セール|即日|正規品|新品|即納|返品可|国内正規|最大\d+|\d+%OFF|限定|予約)[^】\])）]{0,24}[】\])）]", "", t, flags=re.I)
    t = re.sub(r"^[\s/｜|・]+", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t[:120]


def is_noise(item, brand, ng_words, ng_shop_words):
    title = normalize(item.get("title", ""))
    shop = normalize(item.get("shop", ""))
    if not item.get("image"):
        return "no-image"
    if not item.get("url"):
        return "no-url"
    if item.get("price", 0) < brand.get("min_price", 3000):
        return "cheap"
    for w in ng_words:
        if normalize(w) in title:
            return "ng:" + w
    for w in ng_shop_words:
        if normalize(w) in shop:
            return "ngshop:" + w
    squashed = squash(item.get("title", ""))
    hit = False
    for m in brand.get("match", []):
        if normalize(m) in title or squash(m) in squashed:
            hit = True
            break
    if not hit:
        return "brand-mismatch"
    return None


def dedupe(items):
    """同一商品を複数店舗が出しているケースを1つに寄せる。
    残すのは 報酬率が高い > 安い もの。
    公式ストアはサイズ違い・色違いが別商品として並ぶので、同じ商品名は1枚にする。"""
    best = {}
    for it in items:
        key = (it["brand"], squash(it["title"])[:40], it["category"])
        cur = best.get(key)
        if cur is None:
            best[key] = it
            continue
        a = (float(it.get("affiliate_rate") or 0), -int(it.get("price") or 0))
        b = (float(cur.get("affiliate_rate") or 0), -int(cur.get("price") or 0))
        if a > b:
            best[key] = it
    return list(best.values())


def is_paid(item):
    """報酬が発生するリンクか（楽天アフィリエイトURLかどうか）。"""
    return "hb.afl.rakuten.co.jp" in (item.get("url") or "")


def interleave_weighted(items, ratio=2, key=lambda x: x.get("brand")):
    """新着順を保ったまま、同じ初出日の中で『報酬ありを ratio 件：報酬なし 1 件』で混ぜる。
    ratio=1 なら従来どおり均等。報酬なしを消すのではなく、出る位置を下げるだけ。"""
    out = []
    bucket = []
    current = None

    def rr(rows):
        """ブランドが連続しないよう順番に取り出す。"""
        groups, order, res = {}, [], []
        for r in rows:
            k = key(r)
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(r)
        while order:
            for k in list(order):
                if groups[k]:
                    res.append(groups[k].pop(0))
                if not groups[k]:
                    order.remove(k)
        return res

    def flush(rows):
        paid = rr([r for r in rows if is_paid(r)])
        free = rr([r for r in rows if not is_paid(r)])
        i = j = 0
        while i < len(paid) or j < len(free):
            for _ in range(ratio):
                if i < len(paid):
                    out.append(paid[i]); i += 1
            if j < len(free):
                out.append(free[j]); j += 1
            elif i >= len(paid):
                break

    for it in items:
        day = it.get("first_seen", "")
        if day != current:
            flush(bucket)
            bucket = []
            current = day
        bucket.append(it)
    flush(bucket)
    return out


def interleave(items, key=lambda x: x.get("brand")):
    """同じ初出日の中でブランドを順番に回して、1ブランドの塊が続かないようにする。"""
    out = []
    bucket = []
    current = None
    def flush(rows):
        groups = {}
        order = []
        for r in rows:
            k = key(r)
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(r)
        while order:
            for k in list(order):
                if groups[k]:
                    out.append(groups[k].pop(0))
                if not groups[k]:
                    order.remove(k)
    for it in items:
        day = it.get("first_seen", "")
        if day != current:
            flush(bucket)
            bucket = []
            current = day
        bucket.append(it)
    flush(bucket)
    return out


# ---------- 蓄積DB ----------

def load_db(path):
    if not os.path.exists(path):
        return {"items": {}}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except ValueError:
            return {"items": {}}


def save_db(path, db):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def merge(db, fresh, retention_days, max_items):
    """初出日(first_seen)を保持しながらDBを更新する。これが『新着』の根拠になる。"""
    stamp = today()
    items = db.setdefault("items", {})
    added = 0
    for it in fresh:
        key = it["id"]
        old = items.get(key)
        if old:
            it["first_seen"] = old.get("first_seen", stamp)
        else:
            # 公式ストアは発売日(published_at)が取れるので、それを初出日にする
            it["first_seen"] = it.get("first_seen_hint") or stamp
            added += 1
        it["last_seen"] = stamp
        items[key] = it

    # 一定期間見かけなくなった商品（売り切れ・掲載終了）は落とす
    limit = (now_jst() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    dropped = [k for k, v in items.items() if v.get("last_seen", "") < limit]
    for k in dropped:
        del items[k]

    # 上限を超えたら古い順に切る
    if len(items) > max_items:
        ordered = sorted(items.values(), key=lambda x: (x.get("first_seen", ""), x.get("id", "")), reverse=True)
        keep = set(x["id"] for x in ordered[:max_items])
        for k in list(items.keys()):
            if k not in keep:
                del items[k]
    return added, len(dropped)
