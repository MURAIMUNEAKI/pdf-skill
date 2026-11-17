# -*- coding: utf-8 -*-
"""
PDF → ページ区切りのテキスト（_build/raw/<名前>.txt）

使い方:
  python _build/pdf_to_text.py 資料.pdf <名前>            raw/<名前>.txt を作る（照合用。手で直さない）
  python _build/pdf_to_text.py 資料.pdf <名前> --source   あわせて source/<名前>.txt のひな形を作る
                                                          （1ページ＝1ブロック「@@ p1 p=1」。これを節ごとに切り分けて使う）

raw の形式:  === p.1 === の行のあとに、そのページのテキスト（PDFのページ番号。印字ページではない）
抽出には pdftotext（Poppler）があればそれを、無ければ pypdf を使う（pip install pypdf）。
スキャン画像だけのPDFは文字を抜き出せないので、OCR したテキストを同じ形式で raw/ に置く。
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def extract(pdf):
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, check=True).stdout
        pages = out.decode("utf-8", "replace").split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return pages
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pdftotext（Poppler）も pypdf も見つかりません。どちらかを入れてください（pip install pypdf）")
    return [(pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    pdf, name = Path(args[0]), args[1]
    pages = extract(pdf)
    raw = HERE / "raw" / f"{name}.txt"
    raw.parent.mkdir(exist_ok=True)
    raw.write_text("".join(f"=== p.{i} ===\n{t.strip()}\n" for i, t in enumerate(pages, 1)), encoding="utf-8")
    empty = sum(1 for t in pages if not t.strip())
    print(f"{raw}  {len(pages)}ページ" + (f"（文字の無いページ {empty}：スキャン画像ならOCRが必要）" if empty else ""))
    if "--source" in sys.argv:
        src = HERE / "source" / f"{name}.txt"
        if src.exists():
            print(f"{src} はすでにあるので上書きしません")
            return
        src.parent.mkdir(exist_ok=True)
        src.write_text("".join(f"@@ p{i} p={i}\n{t.strip()}\n\n" for i, t in enumerate(pages, 1)), encoding="utf-8")
        print(f"{src}  （ひな形。段落の改行を整え、節ごとに「@@ id p=N」で切り分ける）")


if __name__ == "__main__":
    main()
