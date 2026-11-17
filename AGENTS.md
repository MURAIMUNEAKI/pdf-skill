# AGENTS.md

このリポジトリは、PDF資料から「原文＋解説」の静的サイトを作るためのスキルです（Codex など AGENTS.md を読むエージェント向けの案内）。

- PDF をもとに解説サイトを作るよう頼まれたら、まず `SKILL.md` を読み、その手順に従う
- 原稿の書式は `references/manuscript-format.md`、設定は `references/site-json.md`、確認は `references/checklist.md`
- サイトは `template/` をコピーして作る。`template/` 自体を書き換えるのは、スキルを改良するときだけ
- 原文の文言は変えない。引用は必ず `{{原文 doc="…" id="…"}}` 経由で入れ、`verify_quotes.py` で「不一致 0 件」を確かめる
- ビルド：`python <サイト>/_build/build.py`、検査：`check_src.py` → `verify_quotes.py`

このリポジトリ自体を変更するとき：`template/` のサンプルで `build.py` → `verify_quotes.py` が通り、`overflow375.html` で over=0 になることを確かめてからコミットする。
