# pdf-skill — PDF資料を「原文＋解説」で読める解説サイトにするスキル

公的機関などの PDF 資料を、**原文をそのまま引用しながら一節ずつ解説する静的サイト**にするための、AIエージェント向けスキルです。
Claude Code・Codex・そのほか SKILL.md / AGENTS.md を読めるエージェントで使えます。人が手順書として読んで使うこともできます。

![デザインのイメージ：白いヘッダー、資料のタブ、濃紺のヒーロー帯、著者バー、左の目次と濃紺の要点カード](docs/screenshot-pc.png)

## できること

- PDF → ページ付きテキスト → 原文ブロック → Markdown 原稿 → **Python 1本でサイトを生成**
- 各節が「質問 → 答え → 原文引用 → 解説 → ポイント → 立場別の確認事項 → よくある疑問」の形になる
- 原文を PDF の文字と**機械照合**して、引用の誤りを 0 件にする
- 用語集と用語の個別ページ、本文から用語への自動リンク、同義語つきのサイト内検索
- 構造化データ（Article・FAQPage・DefinedTerm・パンくず）、OGP 画像、sitemap.xml、llms.txt
- デザインは Google Stitch のデザインシステム「Civic Cyber Sentinel」（濃紺×シアン）を CSS に移植。スマホはハンバーガーメニュー
- 必要なのは Python と `markdown`（OGP 画像に `pillow`、PDF 抽出に `pypdf` か Poppler の `pdftotext`）だけ。サーバー側のプログラムは不要

## 入れ方

### Claude Code

```bash
git clone https://github.com/MURAIMUNEAKI/pdf-skill.git ~/.claude/skills/pdf-skill
```

（プロジェクトだけで使うなら `.claude/skills/pdf-skill` に置く）。
Claude Code に「この PDF を解説サイトにして」と頼むと、スキルが使われます。

### Codex（OpenAI Codex CLI）

```bash
git clone https://github.com/MURAIMUNEAKI/pdf-skill.git ~/.codex/skills/pdf-skill
```

スキル機能を使わない場合は、作業するリポジトリの `AGENTS.md` に次の1行を書きます。

```text
PDFから解説サイトを作るときは ~/.codex/skills/pdf-skill/SKILL.md の手順に従う。
```

### そのほかのエージェント・人が使う場合

このリポジトリをどこかに置き、エージェントに `SKILL.md` を読ませるか、自分で `SKILL.md` の手順どおりに進めます。

## すぐ試す

```bash
pip install markdown pillow pypdf
cp -r pdf-skill/template mysite
python mysite/_build/build.py           # サンプル（架空の「みらい市 防災ハンドブック」）を生成
python mysite/_build/verify_quotes.py   # 照合 13 件、不一致 0 件
cd mysite && python -m http.server 8000 # http://localhost:8000/ を開く
```

自分の資料で作るときは、[SKILL.md](SKILL.md) の手順（PDF をテキストにする → `site.json` → 原稿 → ビルド → 照合 → 確認）に進みます。

## ファイル

```
SKILL.md                     スキルの本体（手順・守ること）
AGENTS.md                    Codex など AGENTS.md を読むエージェント向けの案内
references/
  manuscript-format.md       原稿（Markdown）の書き方
  site-json.md               site.json の全項目
  design.md                  デザインの部品・色・スマホの規則
  checklist.md               公開前の確認手順
template/                    サイトのひな形（このフォルダごとコピーして使う）
  _build/build.py            ビルド本体
  _build/site.json           設定（サンプル）
  _build/pdf_to_text.py      PDF → ページ付きテキスト
  _build/check_src.py        原稿の検査
  _build/verify_quotes.py    原文の照合
  _build/overflow375.html    スマホ幅の横はみ出し検査
  _build/src/ source/ raw/   原稿・原文ブロック・PDF抽出テキスト（サンプル）
  assets/style.css site.js   デザインと動き
```

## 注意

- 引用する資料の利用条件（政府標準利用規約、公共データ利用規約、著作権法の引用の要件など）を確認してから使ってください。サンプルの資料・著者・URL は架空です
- 生成したサイトが資料の発行者の公式サイトと誤解されないよう、フッターの注記（`site.json` の `footer_note`）を必ず書いてください
- このスキルは、日本DX応援団の解説サイト「不正アクセス・個人情報漏洩の対策」の作り方を汎用化したものです

## ライセンス

MIT License（[LICENSE](LICENSE)）。テンプレートで作ったサイトの文章・原稿の権利は、それを書いた人にあります。
