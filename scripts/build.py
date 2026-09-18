# -*- coding: utf-8 -*-
"""data/items.json から静的サイトを生成する。"""
import html
import json
import re
import os
import collections
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

ROOT = lib.ROOT
SITE = os.path.join(ROOT, "site")
DB_PATH = os.path.join(ROOT, "data", "items.json")

SCENES = [("street", "STREET"), ("mode", "MODE"), ("outdoor", "OUTDOOR"), ("sneaker", "SNEAKER")]


def load(name):
    with open(os.path.join(ROOT, "config", name), "r", encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape(s or "", quote=True)


def render(tpl, mapping):
    out = tpl
    for k, v in mapping.items():
        out = out.replace("{{%s}}" % k, v)
    return out


def analytics_tag(mid):
    if not mid:
        return ""
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
            'gtag("js",new Date());gtag("config","%s");</script>') % (mid, mid)


def main():
    site = load("site.json")
    conf = load("brands.json")
    db = lib.load_db(DB_PATH)
    raw = list(db.get("items", {}).values())
    if not raw:
        sys.exit("data/items.json が空です。先に python3 scripts/update.py を実行してください。")

    copy = load("brand_copy.json")
    news_db = lib.load_db(os.path.join(ROOT, "data", "news.json"))
    news = sorted(news_db.get("items", {}).values(),
                  key=lambda x: (x.get("date", ""), x.get("title", "")), reverse=True)

    brand_by_id = dict((b["id"], b) for b in conf["brands"])
    cutoff = (lib.now_jst() - lib.timedelta(days=site["new_days"])).strftime("%Y-%m-%d")
    raw.sort(key=lambda x: (x.get("first_seen", ""), x.get("id", "")), reverse=True)
    raw = lib.interleave(raw)  # 同じ日の中で1ブランドが連続しないようにする

    items = []
    counts = {}
    cat_counts = {}
    for it in raw:
        b = brand_by_id.get(it.get("brand"))
        if not b:
            continue
        cid = it.get("category", "acc")
        counts[b["id"]] = counts.get(b["id"], 0) + 1
        cat_counts[cid] = cat_counts.get(cid, 0) + 1
        items.append({
            "i": it.get("image", ""),
            "t": esc(it.get("title", "")),
            "p": int(it.get("price") or 0),
            "u": it.get("url", ""),
            "b": b["id"],
            "bn": esc(b["name"]),
            "c": cid,
            "s": b["scene"],
            "sh": esc(it.get("shop", ""))[:28],
            "n": 1 if it.get("first_seen", "") >= cutoff else 0,
        })

    # トップは新着ぶんだけ載せる（全件はブランド別・カテゴリ別ページに出る）
    top_items = items[:site.get("index_max_items", 800)]
    top_counts = collections.Counter(x["b"] for x in top_items)
    top_cats = set(x["c"] for x in top_items)

    cats = [{"id": c, "label": label} for c, label, _ in lib.CATEGORIES if cat_counts.get(c)]
    top_cat_list = [{"id": c, "label": label} for c, label, _ in lib.CATEGORIES if c in top_cats]
    brands = [{"id": b["id"], "name": b["name"], "scene": b["scene"], "count": counts.get(b["id"], 0)}
              for b in conf["brands"] if counts.get(b["id"])]
    top_brands = [{"id": b["id"], "name": b["name"], "scene": b["scene"], "count": top_counts.get(b["id"], 0)}
                  for b in conf["brands"] if top_counts.get(b["id"])]
    scenes = [{"id": s, "label": l} for s, l in SCENES]

    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    ptpl = open(os.path.join(ROOT, "scripts", "page.html"), encoding="utf-8").read()

    base = (os.environ.get("SITE_BASE_URL") or site.get("base_url", "")).rstrip("/")
    updated = db.get("updated_at", lib.today())
    year = lib.now_jst().strftime("%Y")
    og = items[0]["i"] if items else ""
    extra_head = site.get("extra_head", "") + analytics_tag(site.get("analytics_id", ""))
    demo = bool(db.get("demo"))
    disclosure = site["ad_disclosure"]
    if demo:
        disclosure = "※ ダミーデータを表示しています（scripts/demo.py の出力）。" + disclosure

    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "b"))
    os.makedirs(os.path.join(SITE, "c"))

    def link(prefix, path):
        return prefix + path

    def footnav(prefix):
        pairs = [("新着一覧", "index.html"), ("NEWS", "news.html"), ("運営者情報", "about.html"),
                 ("プライバシーポリシー", "privacy.html")]
        return " ".join('<a href="%s">%s</a>' % (link(prefix, p), t) for t, p in pairs)

    def brandlinks(prefix):
        return " ".join('<a href="%sb/%s.html">%s</a>' % (prefix, b["id"], esc(b["name"]))
                        for b in brands)

    def payload(fixed_brand=None, fixed_cat=None, subset=None, brand_list=None, cat_list=None):
        return json.dumps({
            "items": subset if subset is not None else items,
            "brands": brand_list if brand_list is not None else brands,
            "cats": cat_list if cat_list is not None else cats,
            "scenes": scenes,
            "fixedBrand": fixed_brand, "fixedCat": fixed_cat,
        }, ensure_ascii=False, separators=(",", ":"))

    def jsonld(subset, name, url):
        elems = []
        for i, it in enumerate(subset[:30], 1):
            elems.append({
                "@type": "ListItem", "position": i,
                "item": {"@type": "Product", "name": html.unescape(it["t"]),
                         "image": it["i"], "brand": html.unescape(it["bn"]),
                         "offers": {"@type": "Offer", "price": it["p"],
                                    "priceCurrency": "JPY", "url": it["u"]}},
            })
        doc = {"@context": "https://schema.org", "@type": "ItemList",
               "name": name, "url": url, "itemListElement": elems}
        return '<script type="application/ld+json">%s</script>' % json.dumps(doc, ensure_ascii=False)

    def news_block(subset, label="ブランド関連の最新記事"):
        if not subset:
            return ""
        li = []
        for n in subset:
            d = n.get("date", "")
            li.append(
                '<li><a href="%s" target="_blank" rel="noopener nofollow">'
                '<time>%s</time><span class="src">%s</span>'
                '<span class="nt">%s</span></a></li>'
                % (esc(n.get("url", "")), esc(d[5:].replace("-", ".")),
                   esc(n.get("source", "")), esc(n.get("title", ""))))
        return ('<section class="news"><h3>NEWS<span>%s</span></h3><ul>%s</ul></section>'
                % (esc(label), "".join(li)))

    def common(prefix):
        return {
            "SITENAME": esc(site["title"]),
            "TAGLINE": esc(site["tagline"]),
            "UPDATED": esc(updated),
            "DISCLOSURE": esc(disclosure),
            "EXTRA_HEAD": extra_head,
            "OGIMAGE": og,
            "YEAR": year,
            "BRANDLINKS": brandlinks(prefix),
            "FOOTNAV": footnav(prefix),
            "HOME": link(prefix, "index.html"),
            "NEWSHREF": link(prefix, "news.html"),
            "ABOUTHREF": link(prefix, "about.html"),
            "PRIVACYHREF": link(prefix, "privacy.html"),
        }

    urls = []

    def write(relpath, text):
        path = os.path.join(SITE, relpath)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        urls.append(base + "/" + relpath if base else "/" + relpath)

    # ---- トップ ----
    m = common("")
    m.update({
        "TITLE": esc("%s｜%s" % (site["title"], site["tagline"])),
        "DESC": esc(site["description"]),
        "CANONICAL": (base + "/") if base else "index.html",
        "HEADING": "",
        "INTRO": "",
        "NEWS": "",
        "DATA": payload(subset=top_items, brand_list=top_brands, cat_list=top_cat_list),
        "JSONLD": jsonld(top_items, site["title"], base or ""),
    })
    write("index.html", render(tpl, m))

    # ---- ブランド別 ----
    for b in brands:
        subset = [x for x in items if x["b"] == b["id"]]
        title = "%s の新着アイテム一覧｜%s" % (b["name"], site["title"])
        mb = common("../")
        mb.update({
            "TITLE": esc(title),
            "DESC": esc("%s の新着アイテムを毎日自動更新で掲載。現在%d点。" % (b["name"], len(subset))),
            "CANONICAL": "%s/b/%s.html" % (base, b["id"]) if base else "%s.html" % b["id"],
            "HEADING": '<h2 class="pagetitle">%s<span>NEW ARRIVALS</span></h2>' % esc(b["name"]),
            "INTRO": ('<p class="intro">%s</p>' % esc(copy.get(b["id"], ""))) if copy.get(b["id"]) else "",
            "NEWS": news_block([n for n in news if b["id"] in n.get("brands", [])][:6],
                               "%s 関連の最新記事" % b["name"]),
            "DATA": payload(fixed_brand=b["id"], subset=subset),
            "JSONLD": jsonld(subset, title, ""),
            "OGIMAGE": subset[0]["i"] if subset else og,
        })
        write("b/%s.html" % b["id"], render(tpl, mb))

    # ---- カテゴリ別 ----
    for c in cats:
        subset = [x for x in items if x["c"] == c["id"]]
        title = "%s の新着｜%s" % (c["label"], site["title"])
        mc = common("../")
        mc.update({
            "TITLE": esc(title),
            "DESC": esc("人気ブランドの%sの新着だけを毎日自動更新で掲載。現在%d点。" % (c["label"], len(subset))),
            "CANONICAL": "%s/c/%s.html" % (base, c["id"]) if base else "%s.html" % c["id"],
            "HEADING": '<h2 class="pagetitle">%s<span>NEW ARRIVALS</span></h2>' % esc(c["label"]),
            "INTRO": "",
            "NEWS": "",
            "DATA": payload(fixed_cat=c["id"], subset=subset),
            "JSONLD": jsonld(subset, title, ""),
            "OGIMAGE": subset[0]["i"] if subset else og,
        })
        write("c/%s.html" % c["id"], render(tpl, mc))

    # ---- 固定ページ ----
    op = site.get("operator", {})
    catlinks = " ".join('<a href="c/%s.html">%s</a>' % (c["id"], esc(c["label"])) for c in cats)
    about_body = """
<p>{sitename} は、ストリート・モード・スニーカーの人気ブランドの<strong>新着アイテムだけ</strong>を
自動で収集して掲載しているサイトです。1日2回（6時・18時）更新しています。</p>
<h3>掲載の方法</h3>
<ul>
<li>各ECモールが公開しているAPIから新着商品を取得しています。当サイトは商品を販売していません。</li>
<li>掲載している価格・在庫は<strong>取得時点</strong>のものです。購入前に必ず販売ページで最新の情報をご確認ください。</li>
<li>掲載が終了した商品（売り切れ・取扱終了）は自動的に一覧から外れます。</li>
<li>中古・ノベルティ・空箱などは自動的に除外していますが、完全ではありません。</li>
</ul>
<h3>広告について</h3>
<p>{disclosure} 商品リンクを経由して購入された場合、当サイトに紹介料が支払われることがあります。
紹介料は購入者の支払額には影響しません。</p>
<h3>運営者</h3>
<dl>
<dt>運営者</dt><dd>{name}</dd>
<dt>連絡先</dt><dd>{contact}</dd>
<dt>開設</dt><dd>{opened}</dd>
</dl>
<h3>免責事項</h3>
<p>掲載情報の正確性には努めていますが、内容を保証するものではありません。
商品の購入・取引は各販売サイトの規約に基づいて行われ、それにより生じた損害について当サイトは責任を負いかねます。</p>
<h3>カテゴリ</h3>
<p>{catlinks}</p>
""".format(sitename=esc(site["title"]), disclosure=esc(site["ad_disclosure"]),
           name=esc(op.get("name", "")), contact=esc(op.get("contact", "")),
           opened=esc(op.get("opened", "")), catlinks=catlinks)

    privacy_body = """
<h3>アクセス解析</h3>
<p>当サイトでは、サイトの利用状況を把握するためにアクセス解析ツールを使用することがあります。
これらはCookieを利用して匿名のトラフィックデータを収集しており、個人を特定する情報は含みません。
Cookieはブラウザの設定から無効にすることができます。</p>
<h3>アフィリエイトプログラム</h3>
<p>{disclosure} 当サイトの商品リンクは、楽天アフィリエイトをはじめとする第三者配信の
アフィリエイトプログラムを利用しています。これらの事業者が、ユーザーの興味に応じた広告を表示するために
Cookieを使用することがあります。</p>
<h3>個人情報の取り扱い</h3>
<p>当サイトでは、お問い合わせをいただいた場合を除き、氏名・メールアドレス等の個人情報を取得しません。
お問い合わせでお預かりした情報は、返信以外の目的では利用せず、第三者に開示しません。</p>
<h3>リンクについて</h3>
<p>当サイトはリンクフリーです。掲載しているリンク先で提供される情報・サービスについては、
当サイトは責任を負いかねます。</p>
<h3>お問い合わせ</h3>
<p>{contact}</p>
""".format(disclosure=esc(site["ad_disclosure"]), contact=esc(op.get("contact", "")))

    news_rows = []
    for n in news:
        d = n.get("date", "")
        news_rows.append(
            '<li><a href="%s" target="_blank" rel="noopener nofollow">'
            '<time>%s</time><span class="src">%s</span><span class="nt">%s</span></a></li>'
            % (esc(n.get("url", "")), esc(d[5:].replace("-", ".")),
               esc(n.get("source", "")), esc(n.get("title", ""))))
    news_body = ('<div class="newspage"><ul>%s</ul></div>' % "".join(news_rows)) if news_rows \
        else "<p>いま掲載中のブランドに関係する記事はありません。</p>"
    news_body += ("<p class=\"note\">掲載ブランドの名前が見出しに入っている記事だけを、"
                  "FASHIONSNAP・Hypebeast・WWD JAPAN・HOUYHNHNM の公開フィードから自動で集めています。"
                  "見出しと媒体名のみを掲載し、記事本文は転載していません。</p>")

    for fname, heading, lead, body in [
        ("news.html", "NEWS", "掲載ブランドに関係する最新記事", news_body),
        ("about.html", "運営者情報", "このサイトについて／掲載方法／免責事項", about_body),
        ("privacy.html", "プライバシーポリシー", "Cookie・アクセス解析・個人情報の取り扱い", privacy_body),
    ]:
        mp = common("")
        mp.update({
            "TITLE": esc("%s｜%s" % (heading, site["title"])),
            "DESC": esc("%s - %s" % (heading, site["title"])),
            "CANONICAL": "%s/%s" % (base, fname) if base else fname,
            "HEADING": esc(heading), "LEAD": esc(lead), "BODY": body,
        })
        write(fname, render(ptpl, mp))

    # 404（GitHub Pagesが自動で使う）
    m404 = common("")
    m404.update({
        "TITLE": esc("ページが見つかりません｜%s" % site["title"]),
        "DESC": "", "CANONICAL": "", "HEADING": "404",
        "LEAD": "お探しのページは見つかりませんでした。",
        "BODY": '<p><a href="index.html">新着一覧にもどる</a></p>',
    })
    with open(os.path.join(SITE, "404.html"), "w", encoding="utf-8") as f:
        f.write(render(ptpl, m404))

    # ---- 付帯ファイル ----
    with open(os.path.join(SITE, "data.json"), "w", encoding="utf-8") as f:
        json.dump({"updated_at": updated, "items": items}, f, ensure_ascii=False)
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n" + ("Sitemap: %s/sitemap.xml\n" % base if base else ""))
    with open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write("<url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (esc(u), updated[:10]))
        f.write("</urlset>\n")
    open(os.path.join(SITE, ".nojekyll"), "w").close()

    # 独自ドメインを使う場合、GitHub Pages は公開物の中の CNAME を見る。
    # base_url が github.io 以外ならホスト名を書き出す。
    host = ""
    m = re.match(r"^https?://([^/]+)", base)
    if m and not m.group(1).endswith(".github.io"):
        host = m.group(1)
    if host:
        with open(os.path.join(SITE, "CNAME"), "w", encoding="utf-8") as f:
            f.write(host + "\n")
        print("CNAME を出力しました:", host)

    print("生成完了: 総掲載%d件（トップに%d件）/ news %d / brand %d / category %d / 全%dページ"
          % (len(items), len(top_items), len(news), len(brands), len(cats), len(urls) + 1))
    if demo:
        print("! これはダミーデータです。公開前に scripts/update.py で実データに差し替えてください。")
    if "（" in op.get("name", "") or "（" in op.get("contact", ""):
        print("! config/site.json の operator（運営者名・連絡先）が未記入です。ASP審査前に埋めてください。")


if __name__ == "__main__":
    main()
