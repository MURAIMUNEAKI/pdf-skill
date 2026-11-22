# 公開前の確認

## 1. 検査スクリプト

```bash
python _build/check_src.py        # エラー 0（警告は内容を見て判断）
python _build/build.py            # 「built N pages + M term pages」
python _build/verify_quotes.py    # 「不一致 0 件」
```

## 2. ローカルで表示する

```bash
cd mysite && python -m http.server 8000
```

`http://localhost:8000/` を開く（`file://` だとサイト内検索が動かない）。

- トップ・本文ページ・用語集・用語ページ・検索（`search.html?q=語`）を開く
- 目次のリンク、左の目次の現在地（スクロールでシアンに変わる）、「原本（PDF）を開く」、出典の［n］リンク
- 検索欄に用語を入れて候補が出る、同義語でもヒットする

## 3. PC とスマホの見た目

ブラウザの開発者ツールで 1280px と 375px を見る。ヘッドレス Chrome なら：

```bash
chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1280,1600 --screenshot=pc.png http://localhost:8000/<slug>.html
```

（`--window-size` の幅は 500px 未満にできないことがあるので、375px は開発者ツールか下の検査ページで見る）

## 4. スマホの横はみ出し検査（全ページ）

ローカルサーバーを立てたまま `http://localhost:8000/_build/overflow375.html` を開く。
sitemap.xml の全ページを 375px の枠で順に開き、`scrollWidth` が 375 を超えたページと、はみ出している要素を表示する。
`DONE N pages, over=0` になればよい。
あわせて、解説欄（「わかりやすい解説」）の顔写真が見出しの帯からはみ出して本文に重なっていないかも調べる。特定のページだけ見るときは `overflow375.html#a.html,b.html`。

はみ出しのよくある原因：長いURL・英単語（→ `overflow-wrap:anywhere`）、幅指定の画像・表、`<pre>`。

## 4-2. リンク・構造化データ・アクセス解析

```python
# サイトのフォルダで実行。リンク切れ（存在しないファイル・アンカー）と、JSON-LD が読めないページを出す
import re, json, pathlib
files = {p.name: p.read_text(encoding="utf-8") for p in pathlib.Path(".").glob("*.html")}
ids = {n: set(re.findall(r'id="([^"]+)"', t)) for n, t in files.items()}
for n, t in files.items():
    for f, a in re.findall(r'href="([^"#:?]*\.html)?(#[^"]*)?"', t):
        if f and f not in files: print("no file", n, f)
        elif a and len(a) > 1 and (f or n) in ids and a[1:] not in ids[f or n]: print("no anchor", n, f + a)
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        json.loads(m)
print("ok")
```

GA を入れるときは、`grep -L "<測定ID>" *.html` で何も出ない（全ページに入っている）ことを確かめる。ストリームIDはGAの管理画面の番号で、ページには書かない。

検索結果に出る説明文（meta description）が短すぎ・長すぎでないかも確かめる（目安 50〜200字。検索ページは除く）。用語ページは最初の段落を使い、70字未満なら2段落目まで足す（`build.py` の `term_lead`）。それでも短い用語は、用語集の最初の段落を1〜2文足す。

```python
import re, glob, html
for f in glob.glob("*.html"):
    m = re.search(r'<meta name="description" content="([^"]*)"', open(f, encoding="utf-8").read())
    d = html.unescape(m.group(1)) if m else ""
    if f != "search.html" and not 50 <= len(d) <= 200: print(f, len(d))
```

## 5. 公開後

- 本番URLで数ページ表示する（CSS/JS のキャッシュは `?v=<ハッシュ>` で自動更新される）
- Google の「リッチリザルト テスト」で FAQ・パンくずの構造化データを確かめる
- sitemap.xml を Search Console に送る（親サイトの sitemap.xml に足したときは、親のほうを送り直す）
- 親サイトの sitemap.xml が、ドメイン直下の robots.txt（`Sitemap:` 行）かドメイン直下のサイトマップ索引（sitemapindex）に載っているかも確かめる。載っていなければ、親サイトの sitemap.xml を Search Console に直接登録する

## よくある失敗（実例）

- **スマホで解説欄の顔写真が本文の1行目に重なる**：`style.css` の末尾にある「Stitch デザイン」の層は、PC用の指定（顔写真48px・解説欄の上の余白0）を、それより前に書いたスマホ用の指定より後ろで上書きしている。スマホ用の見た目を変えるときは、**ファイルの最後の `@media (max-width:720px)` の中**に書く（前の方のスマホ用ブロックに書いても、後ろの PC 用の指定に負ける）。直したら上の検査ページで over=0 を確かめる
- **検査ページで多くのページが scrollWidth 1400 前後と出る**：`style.css` が読み込めていない（ローカルサーバーやキャッシュの一時的な失敗）。そのページだけ `#a.html` で再検査する
