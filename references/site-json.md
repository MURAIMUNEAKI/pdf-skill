# site.json の項目

`template/_build/site.json` がサンプル。空文字・省略で機能が消えるものは「任意」。

## site

| キー | 意味 |
|---|---|
| `name` | サイト名（ヘッダー・`<title>` の末尾・パンくずの先頭） |
| `sub` | サイトの副題（OGP・llms.txt） |
| `brand_sub` | 任意。ヘッダーのサイト名の上の小さな札（運営者名など） |
| `base_url` | 公開URL（末尾 `/`）。canonical・sitemap・構造化データに使う |
| `published` | 公開日 `YYYY-MM-DD` |
| `modified` | 任意。更新日。空ならビルドした日 |
| `ga_id` | 任意。Google アナリティクスの測定ID |
| `icon` | ヘッダーのマーク：`shield` / `book` / `doc` / `scale` |
| `logo_char` | ファビコン・ロゴの1文字（既定はサイト名の1文字目） |
| `hero_image` | 任意。各ページの題名の下の横長の画像（例 `assets/hero.jpg`、同名の `.webp` があれば併用）。空なら濃紺の格子の帯 |
| `about` | 構造化データの about（主題）の語 |
| `audience` | 任意。想定読者（構造化データ） |
| `copyright` | フッターの著作権表示 |
| `footer_note` | フッターの注記（HTML可）。「公式サイトではありません」などを書く |
| `license_name`, `license_url` | 任意。引用した資料の利用規約（例：公共データ利用規約（第1.0版）） |
| `credit_note` | 出典欄の「どこまでが原文で、どこからが解説か」の説明 |
| `ogp_label` | トップページのOGP画像の札 |
| `ogp_font_bold`, `ogp_font_regular` | 任意。OGP画像の日本語フォントのパス（見つからないときに指定） |

## author / publisher

`author`：`name`、`url`（任意）、`label`（例「本記事の著者」）、`title`（肩書き）、`bio`（紹介文）、`image`（顔写真のURL。任意）。
`publisher`：`name`、`url`。

## cta（任意）

ヘッダー右のボタン・著者バーのボタン・ページ下の帯・左の列・用語ページに出す、外部への案内。
`label`（ボタンの文字）、`sub`（小さい説明）、`url`、`emoji`、`kicker`（帯の上の小見出し）、`band_title`、`band_lead`（帯の本文。`band_title` が空なら帯は出ない）、`side_title`。
`cta` を `{}` にすると全部消える。

## side_links / related_links（任意）

`[{"label": "...", "url": "..."}]`。`side_links` は左の列とスマホメニュー、`related_links` はフッターの最後のグループに並ぶ。

## docs

引用する資料。キー（例 `doc1`）を原稿の `docs:` と `{{原文 doc="doc1"}}` で使う。

| キー | 意味 |
|---|---|
| `file` | `source/` の原文ブロックのファイル |
| `raw` | `raw/` のPDF抽出テキスト（既定は `file` と同じ名前） |
| `offset` | raw のページ番号 − 原文ブロックの `p=`（表紙を数えないPDFなどで使う。既定 0） |
| `plabel` | 任意。編ごとの印字ページ `[[開始PDFページ, "ⅱ", 差], ...]`（大きい順） |
| `org`, `title`, `date`, `url` | 発行者・資料名・日付・PDFのURL（出典・「原本を開く」ボタン） |
| `short` | 発行者の短い名前 |
| `main` | 出典の一覧・トップの isBasedOn に含めるか（既定 true） |
| `ignore_lines` | 任意。照合で無視する行の正規表現（ヘッダー・フッター・「別紙」など） |

## groups

`[{"name": "グループ名", "tab": "タブの文字"}]`。並び順が目次・フッター・タブの順になる。
`tab` が同じグループは、ヘッダーの1つのタブにまとまる（リンク先は最初のグループの先頭ページ）。
**最後のグループは「付録」扱い**（llms.txt で分けて書き、`related_links` が入る）。

## pages

`[{"slug", "src", "short", "group", "seo", "desc", "keywords"}]`。並び順が前後のページの順。

| キー | 意味 |
|---|---|
| `slug` | ファイル名（`slug.html`） |
| `src` | 原稿 `src/` のファイル名 |
| `short` | 目次・パンくず・ヒーロー帯に出す短い名前 |
| `group` | `groups` の `name` |
| `seo` | 題名と `<title>`（`｜` と途中の `？` で改行。manuscript-format.md 参照） |
| `desc` | meta description（120字前後） |
| `keywords` | 主要キーワード。先頭が「〇〇とは」だと用語ページとの役割分担に使われる |

## roles / role_tags

`roles`：`[{"heading": "職員が確認すること", "cls": "staff|vendor|exec", "icon": "🏛", "label": "画面での見出し"}]`。原稿の `### <heading>` を色付きの確認ボックスにする。
`role_tags`：題名の上の「読む人」の札の色。`{"vendor": "正規表現", "exec": "正規表現"}`。どちらにも合わない札は青（staff）。

## glossary / search / home / その他

- `glossary`：`slug`（用語集ページの slug。既定 `yougo`）、`set_name`（用語集の名前）、`kicker`（用語ページの題名の上の小さな文字）
- `search`：`placeholder`、`tips`、`desc`
- `llms_intro`：llms.txt の冒頭の説明
- `genbun_heading_regex`：任意。原文の中で太字の見出しにする行の正規表現
- `home`：トップページ。`title`、`desc`、`keywords`、`eyebrow`、`h1`（`<br>` 可）、`h1_sub`、`lead`（HTML可）、`image`・`image_alt`（右側の正方形の画像。任意）、`buttons`（`label`/`href`/`primary`）、`who`（読む人別の入口 `label`/`href`/`text`）、`points_title`・`points`（`q`/`a`/`links`。FAQの構造化データにもなる）、`doc_cards`（`slug`/`org`/`date`/`title`/`text`）
