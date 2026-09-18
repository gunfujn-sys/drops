# DROPS — 人気ブランドの新着だけを自動掲載するサイト

毎日決まった時刻に各ブランドの新着アイテムを取得し、静的サイトを生成して公開します。
リンクはすべてアフィリエイトリンク（`rel="nofollow sponsored"`）。

## 仕組み

```
scripts/update.py   2つの取得元から集めて → ノイズ除去 → data/items.json に蓄積
   ├ sources/shopify.py        ブランド公式ストア。認証不要で今すぐ動く。報酬は出ない
   └ sources/rakuten.py        楽天市場API。RAKUTEN_APP_ID があるときだけ。報酬が出る
scripts/news.py     RSS 4媒体 → 掲載ブランドに関係する記事だけを data/news.json に蓄積
scripts/build.py    data/items.json + data/news.json → site/ に静的HTMLを生成
                    （トップ / ブランド別 / カテゴリ別 / 運営者情報 / プライバシーポリシー / 404）
.github/workflows/  毎日 06:00 / 18:00 JST に上記を実行して GitHub Pages に公開
```

**「新着」の判定**は `data/items.json` に記録した初出日（`first_seen`）で行います。
毎回の取得結果と突き合わせて、初めて見た日から7日以内のものに `NEW` を付け、
21日間見かけなくなった商品（売り切れ・掲載終了）は自動で落とします。

## 最初のセットアップ

### 1. 楽天のIDを2つ取る（無料・審査なし・10分）

| 種類 | 取得先 | 用途 |
|---|---|---|
| アプリID | https://webservice.rakuten.co.jp/ | APIを叩くため |
| アフィリエイトID | https://affiliate.rakuten.co.jp/ | 報酬を受け取るため |

### 2. ローカルで試す

```bash
export RAKUTEN_APP_ID=xxxxxxxxxxxxxxxx
export RAKUTEN_AFFILIATE_ID=xxxxxxxx.xxxxxxxx.xxxxxxxx.xxxxxxxx
python3 scripts/update.py      # 商品取得（全ブランドで5〜10分ほど。楽天は1秒1リクエスト）
python3 scripts/news.py        # ニュース取得（数秒）
python3 scripts/build.py       # site/ を生成
open site/index.html
```

1ブランドだけ試す場合： `python3 scripts/update.py --brand=supreme`
APIキー無しで見た目だけ確認： `python3 scripts/demo.py && python3 scripts/build.py`

### 3. GitHubに上げて自動更新にする

```bash
git init && git add -A && git commit -m "init"
# GitHub側でリポジトリを作ってから
git remote add origin https://github.com/<ユーザー名>/drops.git
git branch -M main && git push -u origin main
```

**リポジトリは public にすること。** GitHub Pages を無料プランで公開するには公開リポジトリが必要です
（private で Pages を使うには有料プランが要ります）。楽天のIDは Secrets に入れるので、
public でも外から見えません。

- リポジトリの **Settings → Secrets and variables → Actions** に
  `RAKUTEN_APP_ID` と `RAKUTEN_AFFILIATE_ID` を登録
- 同じ画面の **Variables** に `SITE_BASE_URL`（例 `https://<ユーザー名>.github.io/drops`）
- **Settings → Pages → Source** を **GitHub Actions** に
- Actions タブから `update-and-deploy` を手動実行して初回公開

## 取得元を足す

### ブランド公式ストア（`config/stores.json`）

多くのブランド公式ストアは Shopify で、`https://ドメイン/products.json` が認証なしで読めます。
新しい順に返るので、1リクエストで新着が取れます。追加する前に必ず確認すること：

```bash
curl -sL "https://ブランドのドメイン/products.json?limit=3" | head -c 400
curl -sL "https://ブランドのドメイン/robots.txt" | grep -A2 "User-agent: \*"
curl -sL "https://ブランドのドメイン/meta.json" | grep -o '"currency":"[A-Z]*"'
```

- JSONが返れば使えます。404/403なら別ドメインを探すか諦める
- robots.txt は Shopify 標準（全面禁止は `Nutch` のみ）。`User-agent: *` に `Disallow: /` があったら使わない
- **通貨がJPY以外の店は入れない**（Dover Street Market はGBPなので見送りました）
- 掲載するのは商品名・価格・画像URL・公式ページへのリンクだけ。本文（body_html）は使わない

確認済みで使えなかった先：HUMAN MADE（403）、Supreme（403）、NEPENTHES/NEEDLES、COMOLI、
AURALEE、UNDERCOVER、COOTIE、stein、TOGA、ATTACHMENT、ASICS、Salomon、HOKA、On（いずれもエンドポイント無し）。
これらは楽天から取ります。

### 注意：`published_at` は発売日ではない

ストアが再公開した日付です（Stüssyは250点すべてが同じ日付になっていました）。
新着の判定はあくまで `data/items.json` の `first_seen`（自前の初出記録）で行っています。

## ニュース欄について

`config/news.json` の4媒体（FASHIONSNAP / Hypebeast / WWD JAPAN / HOUYHNHNM）のRSSから、
**掲載ブランドの名前が見出しに入っている記事だけ**を拾います。
掲載するのは見出し・媒体名・日付・リンクのみで、本文と画像は転載しません。

ブランド名が短くて誤爆する場合は `config/brands.json` に `news_match` を足して
照合語を明示してください（Onで「ディオン」「ニッポン」に当たったため実際に使っています）。

## 公開前に埋めるもの

`config/site.json` の `operator`（運営者名・連絡先）。空のままだと生成時に警告が出ます。
ASPの審査では「運営者情報」「プライバシーポリシー」の有無を見られるため、
`site/about.html` と `site/privacy.html` を自動生成しています。

ダミーデータのまま生成すると、サイト上部に「ダミーデータを表示しています」と出ます。
公開前に `scripts/update.py` で実データに差し替えてください。

## 掲載ブランドを変える

`config/brands.json` を編集するだけです。

```json
{"id":"kapital","name":"KAPITAL","scene":"street",
 "keyword":"KAPITAL キャピタル","match":["kapital","キャピタル"],
 "genres":["mens"],"min_price":10000}
```

- `keyword` … 楽天に投げる検索語
- `match` … 商品名にこの語のどれかが無ければ捨てる（別ブランドの混入よけ）
- `min_price` … これ未満は捨てる（ステッカーや小物のノイズよけ）
- `ng_words` … 中古・ノベルティ・空箱などを全ブランド共通で除外
- `news_match` … （任意）ニュース照合を別の語で行う

ブランドを足したら `config/brand_copy.json` に紹介文も足してください（無くても動きます）。

## 収益を伸ばす順番

1. **楽天**（今ここ）— 審査なしで即日。まずサイトの実体を作る
2. **バリューコマース** — 登録してサイト審査 → LinkSwitch のJSタグを
   `config/site.json` の `extra_head` に貼る。ZOZOTOWN・Yahoo!ショッピングと
   提携できると、直リンクが自動でアフィリエイトリンクに変わる
3. **もしもアフィリエイト** — Amazon + 楽天のW報酬
4. **A8.net** — BEAMS / UNITED ARROWS など公式ECは料率が一番高い層

## 注意

- 価格・在庫は取得時点のもの。フッターに明記済み
- ステマ規制（景表法）対応として、ヘッダー直下とフッターに広告表記を常時表示しています
- 楽天APIは1秒1リクエストが目安。`scripts/sources/rakuten.py` の `SLEEP` で調整
