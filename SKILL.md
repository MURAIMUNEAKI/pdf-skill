---
name: pdf-skill
description: 公的機関などのPDF資料をもとに、「原文の引用＋解説＋確認事項＋Q&A＋用語集」で読める静的な解説サイト（濃紺×シアンの Stitch「Civic Cyber Sentinel」デザイン）を作るスキル。PDF→ページ付きテキスト→原文ブロック→Markdown原稿→Pythonでビルド（HTML・検索・sitemap・llms.txt・OGP・構造化データ）→原文の照合→PC/スマホ確認、までの手順とテンプレート一式。「このPDFを解説サイトにして」「資料を原文と解説で読めるページにして」と頼まれたときに使う。
---

# PDF解説サイト・スキル

PDF資料（法令・ガイドライン・白書・通知・社内規程など）を、**原文をそのまま引用しつつ、一節ずつ解説する**静的サイトにする。
出来上がるサイトの特徴：

- 各節＝「Q（この節が答える質問）→ A（答え）→ 原文引用 → 著者の解説 → ポイント → 立場別の確認事項 → よくある疑問」
- 原文はPDFから抜き出した文字と**機械照合**して、一字一句の引用ミスを防ぐ（`verify_quotes.py`）
- 用語集と用語ごとの個別ページ、本文からの自動リンク、サイト内検索（同義語つき）
- SEO/AEO：Article（`spatialCoverage`＝事例の地域、`relatedLink`＝関連ページ、`speakable`）・FAQPage・DefinedTerm・BreadcrumbList・ItemList（トップの一覧表）の JSON-LD、OGP画像、sitemap.xml、llms.txt / llms-full.txt。記事の最後に「あわせて読みたい」カード、トップに事例・章の一覧表
- デザイン：白いヘッダー＋盾マーク、右上のハンバーガー（資料のまとまり＋記事の目次。`header_nav: "tabs"` で従来のタブ）、パンくず帯、濃紺のヒーロー帯、著者バー、左の目次カード（スクロール追従）、濃紺の要点カード、カード型の節、濃紺見出しの表。スマホ（720px以下）はハンバーガーメニューにまとめる
- 依存は Python（`markdown`、OGP画像を作るなら `pillow`）だけ。CSS/JS は自前（Tailwind などのCDN不要）

## このスキルのファイル

| パス | 中身 |
|---|---|
| `template/` | サイトのひな形。**このフォルダごとコピーして使う** |
| `template/_build/build.py` | ビルド本体。設定はすべて `site.json` |
| `template/_build/site.json` | サイト名・URL・著者・資料・ページ・グループ・トップページの文言 |
| `template/_build/pdf_to_text.py` | PDF → `raw/<名前>.txt`（`=== p.N ===` 区切り）と `source/` のひな形 |
| `template/_build/check_src.py` | 原稿の書式と `{{原文}}` 指定の検査 |
| `template/_build/verify_quotes.py` | 原文ブロックがPDFの文字と一致するかの照合 |
| `template/_build/src/` | 原稿（Markdown）。サンプルは架空の「みらい市 防災ハンドブック」 |
| `template/assets/style.css`, `site.js` | デザインと動き（目次の現在地・検索・右上とスマホのメニュー・表のカード化） |
| `template/_build/.gitignore` | `__pycache__/` と元のPDF（`source.pdf`）をコミットしない |
| `references/manuscript-format.md` | **原稿の書き方（必読）** |
| `references/site-json.md` | `site.json` の全項目 |
| `references/design.md` | デザインの部品・色・スマホの規則 |
| `references/checklist.md` | 公開前の確認手順（照合・PC/スマホ・はみ出し検査） |

## 手順

### 1. ひな形をコピーする

```bash
cp -r <このスキルのフォルダ>/template ./mysite      # 出力先＝サイトのフォルダ
pip install markdown pillow pypdf
```

サンプルのまま一度 `python mysite/_build/build.py` を実行し、`mysite/index.html` が出ることを確かめてから書き換える。
サンプルの原稿（`src/*.md`）・原文（`source/sample.txt`・`raw/sample.txt`）は、自分の資料に置き換えたら消す。

### 2. PDF をテキストにする

```bash
python mysite/_build/pdf_to_text.py 資料.pdf doc1 --source
```

- `raw/doc1.txt`：照合用。**手で直さない**（PDFの文字そのもの）
- `source/doc1.txt`：1ページ＝1ブロックのひな形。これを節の単位に切り分けて `@@ <id> p=<ページ>` を付け直し、改行・箇条を読みやすく整える（**文言は変えない**）
- 原文ブロックは、章ごとのファイル（`source/doc1_1.txt`、`doc1_2.txt` … ＝資料のファイル名＋`_`）に分けてもよい。`build.py` が `doc1.txt` と合わせて読む。章を並行して書くときに便利（下の「大きな資料を並行して作る」）
- `p=` には**印字ページ**（資料に印刷されたページ番号）を書き、PDFのページとの差を `offset` で合わせると、読者が原本で探しやすい
- PDFのページ番号と印字ページがずれる資料は、`site.json` の `offset`（raw のページ − `p=` の値）か `plabel` で合わせる
- スキャン画像だけのPDFは文字が取れない。OCRしたテキストを同じ形式で `raw/` に置く

### 3. site.json を書く

`references/site-json.md` を見ながら、サイト名・公開URL（`base_url`）・公開日・著者・資料（`docs`）・グループ・ページ・トップページの文言を書く。
ページは「1ページ＝資料の1章ぐらい（節が3〜8個）」を目安に分ける。事例集なら「1ページ＝1事例」。
事例・地域を扱うページには `place`（地域名）と `related`（関連ページの slug を2〜3個）を書く。トップには `home.cases`（事例・章の一覧表）を書く。

### 4. 原稿を書く

`references/manuscript-format.md` の書式で `src/NN_名前.md` を書く。要点：

- 先頭にフロントマター（`docs` `where` `actors`）、`# 題名`、導入文1段落
- `## N-まとめ` に要点、`## N-1 節の題名` から本文の節、最後に任意で `## N-参考`
- 各節に `> この節が答える質問：…`、原文は `{{原文 doc="doc1" id="ブロックid"}}`、そのあと `### 解説` `### ポイント`、必要なら確認事項・よくある疑問・図解
- **原文の引用は必ず `{{原文}}` 経由で入れる**（原稿に直接貼らない。照合できなくなる）
- 解説は資料に書いてあることと、著者の見解・補足を区別する。資料に無い数字や断定を書かない

### 5. ビルドと検査

```bash
python mysite/_build/check_src.py       # 原稿の書式・原文ブロックの有無
python mysite/_build/build.py           # HTML などを生成
python mysite/_build/verify_quotes.py   # 原文の照合。「不一致 0 件」になるまで source/ を直す
```

不一致が出たら、`source/` のブロックを `raw/` の該当ページと見比べて直す（よくある原因：全角／半角以外の表記ゆれ、ページ番号のずれ、ヘッダー・脚注の混入 → `ignore_lines`）。

### 大きな資料を並行して作る（任意）

章が多い資料は、最初の1〜2ページを作って見た目と書き方の水準を利用者に確認してもらってから、残りを章ごとに並行して書くと早い（Claude Code ならサブエージェント／フォークを章の数だけ起動）。

- 先に `site.json` に全ページの `pages` を登録し、各原稿をスタブ（フロントマター・題名・1節だけ）で作っておく。そうすると、どの担当者もビルドと照合を回せる
- 担当ごとに書くファイルを分ける：原文は `source/doc1_1.txt` のような章ごとのファイル、原稿は自分の章の `src/*.md` だけ。`site.json`・用語集・同義語は**触らせず**、`seo`／`desc`／`keywords`、追加する用語、同義語の行、トップのQ&Aを報告させて、最後に1人でまとめる（同じファイルを同時に書くと壊れる）
- 原文のブロックIDは章ごとの接頭辞（`shiga-*` など）にして重ならないようにする
- まとめたあと、用語の重複（同じ用語を2つの章が出す）を1つにする

### 6. 表示を確かめる

`references/checklist.md` の手順で、ローカルサーバー（`python -m http.server`）を立て、PC（1280px）とスマホ（375px）で確認する。
全ページの横はみ出し検査（`_build/overflow375.html`）で、はみ出し 0 ページにする。
あわせて、サイト内リンクとアンカーのリンク切れ、全ページの JSON-LD が JSON として読めること、GA の測定IDが全ページに入っていることを確かめる（`checklist.md`）。

### 7. 公開

サイトのフォルダ（`_build/` を除いてもよい）を静的ホスティングに置く。`_build/` を公開サーバーに置く場合は、中身（原稿・原文）が見えても困らないか確認する。

- 元のPDFと `__pycache__` はコミットしない（`_build/.gitignore`）
- 親サイトがあるときは、親の `sitemap.xml` にもトップと本文ページを足す（OGP画像を `image:image` で添える）。公開後に Search Console へ sitemap を送り直す
- 同じフォルダで別の作業（別のセッション）がブランチを切り替えていることがある。コミットの前に `git branch --show-current` を確かめる。心配なら `git worktree add` で別フォルダを作って作業する

## 守ること

- **原文の文言は変えない**。整形（改行・箇条・表）だけ。省略するときは省略したことを書く
- 出典（発行者・資料名・日付・URL）と利用条件（政府標準利用規約・公共データ利用規約など）を `site.json` の `docs` / `license_*` / `credit_note` に正しく書く。利用条件が引用・加工を認めていない資料はサイトにしない
- サイトが資料の発行者の公式サイトだと誤解されない書き方にする（`footer_note`）。発行者のロゴや名義を使わない
- APIキー・アクセス解析ID・個人情報を原稿や `site.json` に書いてリポジトリに入れない（GA の ID は公開してよいものだけ）
- 生成物（`*.html`、`*.md`、`ogp/` など）は `build.py` が毎回上書きする。手で直すのは `_build/` の中だけ
