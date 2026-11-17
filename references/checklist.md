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
`DONE N pages, over=0` になればよい。特定のページだけ見るときは `overflow375.html#a.html,b.html`。

はみ出しのよくある原因：長いURL・英単語（→ `overflow-wrap:anywhere`）、幅指定の画像・表、`<pre>`。

## 5. 公開後

- 本番URLで数ページ表示する（CSS/JS のキャッシュは `?v=<ハッシュ>` で自動更新される）
- Google の「リッチリザルト テスト」で FAQ・パンくずの構造化データを確かめる
- sitemap.xml を Search Console に送る
