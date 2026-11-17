# -*- coding: utf-8 -*-
"""
原稿（_build/src/*.md）の書式と {{原文 ...}} 指定を検証する（ファイルは書き出さない）

使い方:  python _build/check_src.py                 （src/ のすべての原稿）
         python _build/check_src.py src/10_第1章.md  （指定した原稿だけ）
各 {{原文}} について「資料とページ｜先頭…末尾（字数）」を表示し、ブロックが見つからない場合はエラーにする。
節の見出し形式・必須要素（この節が答える質問・解説・ポイント）も簡易チェックする。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  （モジュール読み込みのみ。main() は実行しない）


def check(path):
    text = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
    ok = True
    print(f"=== {path}")
    if not text.startswith("---\n"):
        print("  [警告] フロントマター（--- で囲む）がありません")
    if not re.search(r"^# .+", text, re.M):
        print("  [エラー] H1（# 見出し）がありません")
        ok = False
    for m in build.DIRECTIVE.finditer(text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        try:
            out = build.genbun(attrs)
        except Exception as e:  # noqa: BLE001
            print(f"  [エラー] {m.group(0)} → {e}")
            ok = False
            continue
        head = out.splitlines()[0]
        flat = "".join(ln for ln in out.split("\n\n")[1:] if ln.strip())
        print(f"  {head[-24:]}｜{flat[:24]} … {flat[-20:]}（{len(flat)}字）")
    is_glossary = Path(path).name == next((p[1] for p in build.PAGES if p[0] == build.G_SLUG), None)
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        head = sec.splitlines()[0]
        if is_glossary:
            if not build.TERM_HEAD.match(head):
                print(f"  [エラー] 用語の見出しは「## 用語（よみ）」または「## 用語（よみ）{{slug}}」: ## {head}")
                ok = False
            continue
        if not re.match(r"^\d+-(\d+|まとめ|参考)\s+\S", head):
            print(f"  [エラー] 節見出しの形式が不正（## 1-1 題名 / ## 1-まとめ … / ## 1-参考 …）: ## {head}")
            ok = False
            continue
        if re.match(r"^\d+-\d+", head):
            for need in ("> この節が答える質問", "### 解説", "### ポイント"):
                if need not in sec:
                    print(f"  [警告] {head[:30]}：「{need}」がありません")
    print("  OK" if ok else "  NG")
    return ok


if __name__ == "__main__":
    paths = sys.argv[1:] or [str(p) for p in sorted(build.SRC.glob("*.md"))]
    sys.exit(0 if all([check(p) for p in paths]) else 1)
