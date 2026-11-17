# -*- coding: utf-8 -*-
"""
原文ブロック（_build/source/*.txt）が、元のPDFから抜き出したテキスト（_build/raw/*.txt）の
指定ページに、文言どおり含まれているかを照合する。

使い方:  python _build/verify_quotes.py
比べる前に、両方から空白・改行を除き、全角／半角の違い（NFKC）をそろえる。
表は1セルずつ照合する（列見出しの行は、整理のため補うことがあるので照合しない）。行頭の「・」などの記号は照合に含めない。
資料ごとに、照合のじゃまになる行（ヘッダー・フッター・脚注記号など）を site.json の docs.<資料>.ignore_lines（正規表現の配列）で除ける。
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

RAW = build.HERE / "raw"
BULLET = re.compile(r"^[・•○◦●■□◆◇▪\-–→✓※①-⑳\s]+")


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s", "", s)


def raw_pages(doc):
    x = build.DOCS[doc]
    ignore = [re.compile(r) for r in x.get("ignore_lines", [])]
    pages, cur = {}, None
    for line in (RAW / x["raw"]).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^=== p\.(\d+) ===$", line.strip())
        if m:
            cur = int(m.group(1))
            pages[cur] = []
            continue
        if cur is None:
            continue
        # 各ページ先頭の、印字ページ番号だけの行はページをまたぐ文の照合のじゃまになるので除く
        if not "".join(pages[cur]).strip() and re.fullmatch(r"\s*[-－]?\s*\d{1,3}\s*[-－]?\s*", line):
            continue
        if any(r.fullmatch(line.strip()) for r in ignore):
            continue
        pages[cur].append(line)
    out = {}
    for k, v in pages.items():
        t = norm("\n".join(v))
        # 脚注番号（「(※2)」など）は原文欄では省くことがあるので、照合でも除く
        t = re.sub(r"\(※\d+\)", "", t)
        out[k] = t
    return out


def pieces(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if s.startswith("|"):
            if re.fullmatch(r"\|[\s\-:|]+\|?", s):
                continue
            if i + 1 < len(lines) and re.fullmatch(r"\|[\s\-:|]+\|?", lines[i + 1].strip()):
                continue
            for cell in s.strip("|").split("|"):
                c = BULLET.sub("", cell.strip())
                if c and c not in ("-", "○", "－"):
                    yield from (x for x in re.split(r"\s・|／", c) if x.strip())
            continue
        yield BULLET.sub("", s)


def main():
    bad = total = 0
    for doc, x in build.DOCS.items():
        if doc not in build.SOURCES:
            continue
        if not (RAW / x["raw"]).exists():
            print(f"[注意] {doc}: raw/{x['raw']} が無いので照合できません（pdf_to_text.py で作る）")
            continue
        pages = raw_pages(doc)
        for bid, (pg, text) in build.SOURCES[doc].items():
            a, _, b = pg.partition("-")
            lo, hi = int(a) + x["offset"], int(b or a) + x["offset"]
            hay = "".join(pages.get(n, "") for n in range(lo, hi + 1))
            for piece in pieces(text):
                total += 1
                n = norm(piece)
                if n in hay:
                    continue
                # ページをまたぐ・図の中で語順が分かれる場合に備え、文ごとにも確かめる
                sents = [norm(s) for s in re.split(r"(?<=[。、])", piece) if norm(s)]
                missing = [s for s in sents if s not in hay]
                if not missing:
                    continue
                bad += 1
                print(f"[不一致] {doc} {bid} p={pg}: {piece[:60]}")
                for s in missing[:3]:
                    print(f"          見つからない部分: {s[:60]}")
    print(f"照合 {total} 件、不一致 {bad} 件")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
