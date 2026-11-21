# -*- coding: utf-8 -*-
"""
PDF解説サイト ― 静的サイト生成スクリプト（設定は site.json）

1) _build/src/*.md の {{原文 doc="…" id="…"}} 指定を、_build/source/*.txt の該当ブロック
   （「@@ id p=N」で区切った原文）に置き換えて、サイト直下に *.md（RAG用の完成原稿）を書き出す
2) 完成原稿から、サイト直下に HTML・検索インデックス・sitemap.xml・llms.txt・OGP画像を生成する

使い方:  python _build/build.py
         python _build/verify_quotes.py   （原文ブロックが元のPDFの文言と一致しているかを照合）
必要なもの: Python 3.8+ / pip install markdown pillow（pillow は OGP画像用。無くても HTML は作れる）
"""
import hashlib
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

import markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows でもパイプ先に UTF-8 で出す

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                     # 出力先（サイトのフォルダ）
SRC = HERE / "src"
SOURCE = HERE / "source"
esc = html.escape

CFG = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
S = CFG["site"]
BASE_URL = S["base_url"].rstrip("/") + "/"
SITE_NAME = S["name"]
SITE_SUB = S.get("sub", "")
SITE_FULL = f"{SITE_NAME} ― {SITE_SUB}" if SITE_SUB else SITE_NAME
GA_ID = S.get("ga_id", "")
PUBLISHED = S["published"]
MODIFIED = S.get("modified") or date.today().isoformat()
HERO_IMAGE = S.get("hero_image", "")
LICENSE_NAME, LICENSE_URL = S.get("license_name", ""), S.get("license_url", "")
CTA = CFG.get("cta") or {}
SIDE_LINKS = CFG.get("side_links", [])
RELATED = CFG.get("related_links", [])
A = CFG["author"]
GLOSSARY = CFG.get("glossary", {})
G_SLUG = GLOSSARY.get("slug", "yougo")

# ------------------------------------------------------------------ 引用する資料
# file：source/ の原文ブロック、raw：raw/ のPDF抽出テキスト、offset：raw のページ番号 − 原文ブロックの p= の差
DOCS = CFG["docs"]
for _d in DOCS.values():
    _d.setdefault("raw", _d["file"])
    _d.setdefault("offset", 0)
    _d.setdefault("date", "")
    _d.setdefault("short", _d["org"])
MAIN_DOCS = [d for d, x in DOCS.items() if x.get("main", True)]


def doc_name(d):
    x = DOCS[d]
    return f"{x['org']}「{x['title']}」" + (f"（{x['date']}）" if x["date"] else "")


def doc_credit(d):
    x = DOCS[d]
    link = f'（<a href="{x["url"]}" target="_blank" rel="noopener">{x["url"]}</a>）' if x.get("url") else ""
    return (f'「{esc(x["title"])}」' + (f'（{esc(x["date"])}）' if x["date"] else "") + f'（{esc(x["org"])}）{link}')


CREDIT = ("出典：" + "、".join(doc_credit(d) for d in MAIN_DOCS) + "を加工して作成。"
          + S.get("credit_note", "「原文引用」欄は各資料の文言をそのまま掲載し（改行・箇条・表の体裁を整理）、"
                  "見出し・解説・ポイント・確認事項・Q&amp;Aは解説の著者が作成したもので、資料の発行者が作成したものではありません。"))

AUTHOR = {"@type": "Person", "@id": BASE_URL + "#author", "name": A["name"], "url": A.get("url", BASE_URL),
          "jobTitle": A.get("title", ""), "description": A.get("bio", ""), "image": A.get("image", ""),
          "sameAs": [A["url"]] if A.get("url") else [], "knowsAbout": S.get("about", [])}
PUB = CFG.get("publisher", {"name": A["name"], "url": A.get("url", BASE_URL)})
PUBLISHER = {"@type": "Organization", "@id": BASE_URL + "#org", "name": PUB["name"], "url": PUB.get("url", BASE_URL),
             "logo": {"@type": "ImageObject", "url": BASE_URL + "ogp/logo.png", "width": 512, "height": 512}}

# ------------------------------------------------------------------ ページ定義
GROUPS = CFG["groups"]
GROUP_ORDER = [g["name"] for g in GROUPS]
PAGES = [(p["slug"], p["src"], p["short"], p["group"], p["seo"], p["desc"], p.get("keywords", []))
         for p in CFG["pages"]]
PAGES = [p for p in PAGES if (SRC / p[1]).exists()]
SLUG_INDEX = {p[0]: i for i, p in enumerate(PAGES)}
GLOSSARY_GROUP = next((p[3] for p in PAGES if p[0] == G_SLUG), GROUP_ORDER[-1])


# ------------------------------------------------------------------ 1) 原文の差し込み
def load_source(doc):
    """source/*.txt を {id: (page, text)} に読む"""
    blocks, cur = {}, None
    for line in (SOURCE / DOCS[doc]["file"]).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^@@\s+(\S+)\s+p=([\d\-]+)\s*$", line)
        if m:
            cur = m.group(1)
            blocks[cur] = [m.group(2), []]
            continue
        if cur:
            blocks[cur][1].append(line)
    return {k: (v[0], "\n".join(v[1]).strip()) for k, v in blocks.items()}


SOURCES = {d: load_source(d) for d in DOCS if (SOURCE / DOCS[d]["file"]).exists()}


def page_label(doc, n):
    """印字ページ（例 ⅱ-12）。plabel が無い資料は空文字"""
    for start, vol, base in DOCS[doc].get("plabel", []):
        if n >= start:
            return f"{vol}-{n - base}"
    return ""


def page_span(pages, doc=None):
    nums = []
    for p in pages:
        a, _, b = p.partition("-")
        nums += [int(a), int(b or a)]
    lo, hi = min(nums), max(nums)
    out = f"p.{lo}" + (f"〜{hi}" if hi != lo else "")
    if doc and DOCS[doc].get("plabel"):
        a, b = page_label(doc, lo), page_label(doc, hi)
        out = "PDF " + out + f"・印字ページ {a}" + (f"〜{b}" if b != a else "")
    return out


def genbun(attrs):
    doc = attrs["doc"]
    if doc not in SOURCES:
        raise ValueError(f"資料が site.json の docs に無いか、source/ のファイルがありません: {doc}")
    ids = [i.strip() for i in attrs["id"].split(",") if i.strip()]
    pages, texts = [], []
    for i in ids:
        if i not in SOURCES[doc]:
            raise ValueError(f"原文ブロックが見つかりません: {doc} {i}")
        pg, tx = SOURCES[doc][i]
        pages.append(pg)
        texts.append(tx)
    return "\n".join([f"### 原文（{doc_name(doc)} {page_span(pages, doc)}）", "", "\n\n".join(texts)])


DIRECTIVE = re.compile(r"\{\{原文((?:\s+\w+=\"[^\"]*\")*)\s*\}\}")


def assemble():
    for p in PAGES:
        src = (SRC / p[1]).read_text(encoding="utf-8")

        def rep(m):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            return genbun(attrs)
        (ROOT / p[1]).write_text(DIRECTIVE.sub(rep, src), encoding="utf-8")


# ------------------------------------------------------------------ 原稿の読み込み
def read_md(name):
    t = (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        t = t[m.end():]
    return meta, t


def meta_docs(meta):
    return [d.strip() for d in meta.get("docs", "").strip("[]").split(",") if d.strip() in DOCS]


def split_sections(body):
    h1 = re.search(r"^# (.+)$", body, re.M).group(1).strip()
    parts = re.split(r"^## ", body, flags=re.M)
    intro = re.sub(r"^# .+$", "", parts[0], flags=re.M).strip()
    secs = []
    for p in parts[1:]:
        head, _, rest = p.partition("\n")
        secs.append((head.strip(), rest.strip("\n")))
    return h1, intro, secs


def split_sub(text):
    """'### 名前' ごとに分ける。先頭（### の前）は名前 '' """
    parts = re.split(r"^### ", text, flags=re.M)
    out = [("", parts[0].strip())]
    for p in parts[1:]:
        head, _, rest = p.partition("\n")
        out.append((head.strip(), rest.strip()))
    return out


def pull_meta_lines(text):
    question, related, keep = None, [], []
    for line in text.splitlines():
        s = line.strip()
        if question is None and s.startswith("> この節が答える質問"):
            question = re.sub(r"^>\s*この節が答える質問[：:]\s*", "", s)
            continue
        if s.startswith("関連語：") or s.startswith("関連語:"):
            related = [w.strip() for w in re.split(r"[、,，]", re.split(r"[：:]", s, maxsplit=1)[1]) if w.strip()]
            continue
        keep.append(line)
    return question, related, "\n".join(keep).strip()


# ------------------------------------------------------------------ Markdown → HTML
URL_RE = re.compile(r"(?<![\"'(<=])(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+)")


def fix_lists(text):
    out, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if i > 0:
            prev = lines[i - 1]
            is_block = re.match(r"^\s*([-*+]|\d+\.)\s", line) or line.startswith("|")
            prev_block = re.match(r"^\s*([-*+]|\d+\.)\s", prev) or prev.startswith("|")
            if is_block and prev.strip() and not prev_block:
                out.append("")
        out.append(line)
    return "\n".join(out)


def md_to_html(text):
    text = fix_lists(text)
    text = URL_RE.sub(lambda m: f"<{m.group(1).rstrip('.,')}>", text)
    h = markdown.markdown(text, extensions=["tables", "sane_lists", "md_in_html"], output_format="html5")
    h = h.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    h = re.sub(r'<a href="(https?://[^"]+)">', r'<a href="\1" target="_blank" rel="noopener">', h)
    return h


def plain(text, limit=None):
    t = re.sub(r"<(svg|figure|style)[\s\S]*?</\1>", "", text)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"[*_`>#|]", "", t)
    t = re.sub(r"^\s*[-+]\s+", "・", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    if limit and len(t) > limit:
        cut = t[:limit]
        p = cut.rfind("。")
        t = cut[: p + 1] if p > limit * 0.5 else cut + "…"
    return t


def lead_html(md):
    """冒頭の文は飾りを外した文字で出すが、[文字](https://…) のリンクだけは残す"""
    links = []

    def keep(m):
        links.append((m.group(1), m.group(2)))
        return f"⟦{len(links) - 1}⟧"
    h = esc(plain(re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", keep, md)))
    for i, (txt, url) in enumerate(links):
        h = h.replace(f"⟦{i}⟧", f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(plain(txt))}</a>')
    return h


def first_paragraphs(text, n=2):
    paras = [p for p in re.split(r"\n\s*\n", text)
             if p.strip() and not p.lstrip().startswith(("-", "|", "1.", "#", "<"))]
    return "\n\n".join(paras[:n])


# 原文ブロックの中で「見出し」として太字にする行（項番・括弧書きの小見出しなど）
G_HEAD = re.compile(CFG.get("genbun_heading_regex",
                            r"^([０-９0-9]{1,2}．|（[０-９0-9]+）|【[^】]+】$|＜[^＞]+＞$|第[０-９0-9一二三四五六七八九十]+[章節条]|[０-９0-9] )"))


def genbun_html(text):
    """原文ブロック：見出し行・箇条・表を整形"""
    out = []
    for para in re.split(r"\n\s*\n", text):
        s = para.strip()
        if not s:
            continue
        if s.startswith("|"):
            out.append(md_to_html(s))
            continue
        h = esc(s).replace("\n", "<br>")
        if re.match(r"^[・✓○※→]", s) or re.match(r"^[①-⑳]", s):
            out.append(f'<p class="g-li">{h}</p>')
        elif G_HEAD.match(s) and "。" not in s and len(s) < 70:
            out.append(f'<p class="g-h">{h}</p>')
        else:
            out.append(f"<p>{h}</p>")
    return "".join(out)


# ------------------------------------------------------------------ 用語集（内部リンク用）
KANA = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo", "しゃ": "sha", "しゅ": "shu", "しょ": "sho", "ちゃ": "cha",
    "ちゅ": "chu", "ちょ": "cho", "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo", "ひゃ": "hya", "ひゅ": "hyu",
    "ひょ": "hyo", "みゃ": "mya", "みゅ": "myu", "みょ": "myo", "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo", "じゃ": "ja", "じゅ": "ju", "じょ": "jo", "びゃ": "bya",
    "びゅ": "byu", "びょ": "byo", "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o", "か": "ka", "き": "ki", "く": "ku", "け": "ke",
    "こ": "ko", "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so", "た": "ta", "ち": "chi",
    "つ": "tsu", "て": "te", "と": "to", "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho", "ま": "ma", "み": "mi", "む": "mu",
    "め": "me", "も": "mo", "や": "ya", "ゆ": "yu", "よ": "yo", "ら": "ra", "り": "ri", "る": "ru",
    "れ": "re", "ろ": "ro", "わ": "wa", "を": "o", "ん": "n", "が": "ga", "ぎ": "gi", "ぐ": "gu",
    "げ": "ge", "ご": "go", "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo", "だ": "da",
    "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do", "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be",
    "ぼ": "bo", "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po", "ー": "",
}


def romaji(kana):
    out, i = "", 0
    while i < len(kana):
        two, one = kana[i:i + 2], kana[i]
        if two in KANA:
            out += KANA[two]
            i += 2
            continue
        if one == "っ" and i + 1 < len(kana):
            nxt = KANA.get(kana[i + 1:i + 3]) or KANA.get(kana[i + 1], "")
            out += nxt[:1]
            i += 1
            continue
        out += KANA.get(one, "")
        i += 1
    return out


TERMS = {}
OWNERS = {}
CH_QUESTIONS = set()        # 本文ページのQ&Aに使った質問文（用語ページで重複させない）
TERM_HEAD = re.compile(r"(.+?)（(.+?)）(?:\s*\{([a-z0-9-]+)\})?$")
GLOSSARY_NAME = GLOSSARY.get("set_name", f"{SITE_NAME}の用語集")


def load_terms():
    gp = next((p for p in PAGES if p[0] == G_SLUG), None)
    if not gp:
        return
    _, body = read_md(gp[1])
    _, _, secs = split_sections(body)
    for head, text in sorted_terms(secs):
        m = TERM_HEAD.match(head)
        if m:
            term, reading = m.group(1).strip(), m.group(2).strip()
            slug = f"{G_SLUG}-" + (m.group(3) or romaji(reading) or re.sub(r"[^A-Za-z0-9]", "", term).lower())
            TERMS[term] = {"reading": reading, "text": text, "slug": slug}
    slugs = [v["slug"] for v in TERMS.values()]
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    assert not dup, f"用語ページのファイル名が重複しています（見出しの末尾に {{英字のslug}} を付けて区別）: {dup}"


def sorted_terms(secs):
    """用語を読みの五十音順（英字の用語は先頭）に並べる"""
    def key(sec):
        m = TERM_HEAD.match(sec[0])
        return ("0" if re.match(r"[A-Za-z0-9]", m.group(1)) else "1") + m.group(2) if m else "9"
    return sorted(secs, key=key)


def term_url(word):
    return TERMS[word]["slug"] + ".html"


def term_link(word):
    if word in TERMS:
        return f'<a class="chip" href="{term_url(word)}">{esc(word)}</a>'
    return f'<span class="chip chip-plain">{esc(word)}</span>'


NO_LINK_TAGS = ("a", "h1", "h2", "h3", "h4", "th", "code", "pre", "button", "svg", "figure")
AUTO_RE = None


def autolink(html_text, used, limit=3, exclude=()):
    """本文中の用語を、1節につき limit 個まで用語ページへのリンクにする（同じ語は1回だけ）"""
    if AUTO_RE is None:
        return html_text
    parts = re.split(r"(<[^>]+>)", html_text)
    depth, count, out = 0, 0, []

    def sub(m):
        nonlocal count
        w = m.group(0)
        if w in used or w in exclude or count >= limit:
            return w
        used.add(w)
        count += 1
        return f'<a class="tl" href="{term_url(w)}">{w}</a>'

    for part in parts:
        if part.startswith("<"):
            tag = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            if tag and tag.group(1).lower() in NO_LINK_TAGS and not part.endswith("/>"):
                depth += -1 if part.startswith("</") else 1
            out.append(part)
        elif depth > 0 or count >= limit:
            out.append(part)
        else:
            out.append(AUTO_RE.sub(sub, part))
    return "".join(out)


# ------------------------------------------------------------------ 共通パーツ
ICONS = {
    "shield": '<path d="M12 3l7 3v5c0 4.6-3 8.4-7 10-4-1.6-7-5.4-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5"/><path d="M9 7h6"/>',
    "doc": '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h6"/>',
    "scale": '<path d="M12 3v18M5 21h14M6 7h12"/><path d="M6 7l-3 6a3 3 0 0 0 6 0zM18 7l-3 6a3 3 0 0 0 6 0z"/>',
}
ICON_MAIN = ('<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICONS.get(S.get("icon", "doc"), ICONS["doc"]) + '</svg>')
ICON_SEARCH = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" '
               'stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>')


def asset_ver():
    return hashlib.md5(b"".join((ROOT / "assets" / n).read_bytes() for n in ("style.css", "site.js"))).hexdigest()[:8]


ROBOTS = "index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1"


def head_html(page_title, desc, url, keywords, og_image, jsonld, page_type="article", robots=ROBOTS):
    kw = ",".join(keywords)
    ga = (f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
""" if GA_ID else "")
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
{ga}<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="keywords" content="{esc(kw)}">
<meta name="author" content="{esc(A['name'])}">
<meta name="robots" content="{robots}">
<meta name="theme-color" content="#0b192c">
<link rel="canonical" href="{url}">
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="icon" href="favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="sitemap" type="application/xml" href="sitemap.xml">
<link rel="alternate" type="text/plain" href="llms.txt" title="llms.txt">
<meta property="og:type" content="{page_type}">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:title" content="{esc(page_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ja_JP">
<meta property="article:published_time" content="{PUBLISHED}">
<meta property="article:modified_time" content="{MODIFIED}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(page_title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{og_image}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
<link rel="stylesheet" href="assets/style.css?v={ASSET_VER}">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))}</script>
</head>
"""


def group_of(slug):
    if slug and (slug == G_SLUG or slug.startswith(G_SLUG + "-")):
        return GLOSSARY_GROUP
    i = SLUG_INDEX.get(slug or "")
    return PAGES[i][3] if i is not None else None


def group_tabs(current):
    """ヘッダー2段目のタブ。site.json の groups の tab が同じグループは1つのタブにまとめる"""
    tabs = [("トップ", "./", ())]
    for g in GROUPS:
        label = g.get("tab") or g["name"]
        first = next((p for p in PAGES if p[3] == g["name"]), None)
        if not first:
            continue
        for i, (lb, href, gs) in enumerate(tabs):
            if lb == label:
                tabs[i] = (lb, href, gs + (g["name"],))
                break
        else:
            tabs.append((label, f"{first[0]}.html", (g["name"],)))
    cur = group_of(current)
    out = []
    for label, href, groups in tabs:
        on = (not current and href == "./") or (cur in groups)
        out.append(f'<a href="{href}"{" aria-current=\"page\"" if on else ""}>{esc(label)}</a>')
    return f'<nav class="gtabs" aria-label="資料のまとまり"><div class="wrap gtabs-inner">{"".join(out)}</div></nav>'


def cta_link(cls, inner):
    return f'<a class="{cls}" href="{esc(CTA["url"])}" target="_blank" rel="noopener">{inner}</a>'


def header_html(current=None, minfo=""):
    # 1段目：ロゴ・検索・CTAボタン、2段目：資料のまとまりのタブ（PC・タブレットだけ）
    # スマホ（720px以下）では、検索・CTA・記事の目次・このページの情報をハンバーガーメニューの中に入れる
    nav = cta_link("hbtn", ICON_SEARCH + esc(CTA["label"])) if CTA else ""
    info = f'<div class="mnav-info"><p class="mnav-h">このページ</p>{minfo}</div>' if minfo else ""
    side = "".join(f'<a class="side-databank" href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["label"])}</a>'
                   for x in SIDE_LINKS)
    msec = cta_link("mnav-sec", f'<b>{esc(CTA["label"])}</b><small>{esc(CTA.get("sub", ""))}</small>') if CTA else ""
    brand_sub = f'<span class="brand-sub">{esc(S["brand_sub"])}</span>' if S.get("brand_sub") else ""
    return f"""<body>
<a class="skip" href="#main">本文へスキップ</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="./" aria-label="{esc(SITE_NAME)} トップへ">
      <span class="brand-mark" aria-hidden="true">{ICON_MAIN}</span>
      <span class="brand-text">{brand_sub}<span class="brand-name">{esc(SITE_NAME)}</span></span>
    </a>
    <button class="menu-btn" type="button" aria-controls="hpanel" aria-expanded="false" aria-label="メニューを開く"><span class="mb-bars" aria-hidden="true"><span></span></span><span class="mb-label">メニュー</span></button>
    <div class="hpanel" id="hpanel">
    <form class="hsearch" action="search.html" method="get" role="search" autocomplete="off">
      <label class="sr" for="hq">サイト内検索</label>
      <input id="hq" class="js-search" type="search" name="q" placeholder="{esc(CFG.get('search', {}).get('placeholder', '用語・キーワードで検索'))}">
      <div class="sresults" hidden></div>
    </form>
    <nav class="gnav" aria-label="関連サイト">{nav}</nav>
    <div class="mnav">{info}<nav class="mnav-book" aria-label="記事の目次（メニュー）"><p class="mnav-h">記事の目次</p>{book_nav(current or "")}</nav>
      {side}{msec}</div>
    </div>
  </div>
  {group_tabs(current)}
</header>
"""


def cta_buttons(cls="cta-btns"):
    if not CTA:
        return ""
    return (f'<div class="{cls}">' + cta_link("cta cta-muni", f'<span class="cta-ic">{CTA.get("emoji", "🔍")}</span><span><b>{esc(CTA["label"])}</b>'
                                              f'<small>{esc(CTA.get("sub", ""))}</small></span>') + '</div>')


def cta_band():
    if not CTA or not CTA.get("band_title"):
        return ""
    return (f'<aside class="cta-band" aria-label="ご案内"><p class="cta-kicker">{ICON_SEARCH}{esc(CTA.get("kicker", ""))}</p>'
            f'<p class="cta-title">{esc(CTA["band_title"])}</p>'
            f'<p class="cta-lead">{esc(CTA.get("band_lead", ""))}</p>{cta_buttons()}</aside>')


def footer_html():
    groups = []
    for g in GROUP_ORDER:
        items = "".join(f'<li><a href="{p[0]}.html">{esc(p[2])}</a></li>' for p in PAGES if p[3] == g)
        if g == GROUP_ORDER[-1]:
            items += "".join(f'<li><a href="{esc(x["url"])}">{esc(x["label"])}</a></li>' for x in RELATED)
        if items:
            groups.append(f'<div class="fcol"><p class="fhead">{esc(g)}</p><ul>{items}</ul></div>')
    lic = (f'利用規約：<a href="{LICENSE_URL}" target="_blank" rel="noopener">{esc(LICENSE_NAME)}</a>。' if LICENSE_URL else "")
    return f"""<div class="wrap">{cta_band()}</div>
<footer class="site-footer">
  <div class="wrap">
    <p class="footer-brand"><span class="brand-mark" aria-hidden="true">{ICON_MAIN}</span><a href="./">{esc(SITE_NAME)}</a></p>
    <div class="footer-note">{S.get("footer_note", "")}</div>
    <nav class="footer-nav" aria-label="サイトの目次">{''.join(groups)}</nav>
    <details class="footer-meta acc"><summary>出典・利用規約・クレジット</summary><p>{CREDIT}<br>{lic}この記事は資料の発行者による公式の解説ではありません。最新の内容は各機関の公表資料で確認してください。</p></details>
    <p class="copy">{esc(S.get("copyright", "解説 © " + A["name"]))}　<a href="./">{esc(SITE_FULL)}</a></p>
  </div>
</footer>
<a class="to-top" href="#top" aria-label="ページの先頭へ">↑</a>
<script src="assets/site.js?v={ASSET_VER}" defer></script>
</body>
</html>
"""


def side_cta():
    out = "".join(f'<a class="side-databank" href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["label"])}</a>'
                  for x in SIDE_LINKS)
    if CTA:
        out += cta_link("side-cta", f'<b>{esc(CTA.get("side_title", CTA["label"]))}</b><span>{esc(CTA.get("sub", ""))} →</span>')
    return out


def book_nav(current):
    out = []
    for g in GROUP_ORDER:
        items = [f'<li><a href="{p[0]}.html"{" aria-current=\"page\"" if p[0] == current else ""}>{esc(p[2])}</a></li>'
                 for p in PAGES if p[3] == g]
        if items:
            out.append(f'<p class="bn-group">{esc(g)}</p><ul>{"".join(items)}</ul>')
    return "".join(out)


def breadcrumb_ld(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def breadcrumb_html(items):
    lis = "".join(f'<li><a href="{u}">{esc(n)}</a></li>' for n, u in items[:-1])
    return (f'<nav class="breadcrumb" aria-label="パンくずリスト"><ol>{lis}'
            f'<li aria-current="page">{esc(items[-1][0])}</li></ol></nav>')


def ymd(s):
    return f"{int(s[:4])}年{int(s[5:7])}月{int(s[8:])}日"


def author_link():
    return (f'<a href="{esc(A["url"])}" target="_blank" rel="noopener author">{esc(A["name"])}</a>'
            if A.get("url") else esc(A["name"]))


def byline():
    return (f'<p class="byline">解説：{author_link()}（{esc(A.get("label", "本記事の著者"))}）<span class="sep">｜</span>'
            f'公開 <time datetime="{PUBLISHED}">{ymd(PUBLISHED)}</time>'
            f'<span class="sep">｜</span>更新 <time datetime="{MODIFIED}">{ymd(MODIFIED)}</time></p>')


def crumb_band(crumbs):
    """ヘッダーの下の、パンくずリストの帯"""
    return f'<div class="crumb-band"><div class="wrap">{breadcrumb_html(crumbs)}</div></div>'


def face(cls, size):
    return f'<img class="{cls}" src="{esc(A["image"])}" alt="" width="{size}" height="{size}" loading="lazy">' if A.get("image") else ""


def author_bar(docs=(), toc=False):
    """題名とヒーロー画像の下の帯：著者・公開日／更新日・ボタン（原本・目次・CTA）"""
    btns = []
    if docs and DOCS[docs[0]].get("url"):
        btns.append(f'<a class="ab-btn" href="{DOCS[docs[0]]["url"]}" target="_blank" rel="noopener">原本（PDF）を開く</a>')
    if toc:
        btns.append('<a class="ab-btn ab-toc" href="#page-toc">目次へ</a>')
    if CTA:
        btns.append(cta_link("ab-btn ab-sec", ICON_SEARCH + esc(CTA["label"])))
    title = "・".join(x for x in (A.get("label", "本記事の著者"), A.get("title", "")) if x)
    return (f'<div class="author-bar">{face("ab-face", 48)}'
            f'<div class="ab-who"><p class="ab-line">解説：{author_link()}<small>（{esc(title)}）</small></p>'
            f'<p class="ab-dates">公開 <time datetime="{PUBLISHED}">{ymd(PUBLISHED)}</time><span class="sep">・</span>'
            f'更新 <time datetime="{MODIFIED}">{ymd(MODIFIED)}</time></p></div>'
            f'<div class="ab-btns">{"".join(btns)}</div></div>')


def page_hero(group, short):
    """記事の上の横長の帯（どのページも同じ画像。文字はそのページのまとまりと題名）。画像が無ければ濃紺の地"""
    cap = f'<figcaption><span class="ph-badge">{ICON_MAIN}{esc(group)}</span><span class="ph-title">{esc(short)}</span></figcaption>'
    if not HERO_IMAGE:
        return f'<figure class="page-hero no-img">{cap}</figure>'
    base, ext = HERO_IMAGE.rsplit(".", 1)
    webp = f'<source srcset="{esc(base)}.webp" type="image/webp">' if (ROOT / f"{base}.webp").exists() and ext != "webp" else ""
    return (f'<figure class="page-hero"><picture>{webp}'
            f'<img src="{esc(HERO_IMAGE)}" alt="" width="1376" height="768" fetchpriority="high" decoding="async"></picture>{cap}</figure>')


def author_box():
    img = f'<img src="{esc(A["image"])}" alt="{esc(A["name"])}" width="88" height="88" loading="lazy">' if A.get("image") else ""
    return (f'<aside class="author-box" aria-label="著者紹介">{img}'
            f'<div><p class="ab-label">{esc(A.get("label", "本記事の著者"))}</p>'
            f'<p class="ab-name">{author_link()}</p>'
            f'<p class="ab-title">{esc(A.get("title", ""))}</p>'
            f'<p class="ab-bio">{esc(A.get("bio", ""))}</p></div></aside>')


def voice_html(inner):
    return (f'<div class="voice{"" if A.get("image") else " no-face"}">{face("voice-face", 56)}'
            f'<div class="voice-body"><p class="voice-label">{esc(A.get("label", "本記事の著者"))}の解説</p>{inner}</div></div>')


def pager(slug):
    i = SLUG_INDEX[slug]
    prev = PAGES[i - 1] if i > 0 else None
    nxt = PAGES[i + 1] if i + 1 < len(PAGES) else None
    cells = [f'<a class="pg pg-prev" href="{prev[0]}.html"><span>前のページ</span>{esc(prev[2])}</a>'
             if prev else '<a class="pg pg-prev" href="./"><span>トップへ</span>サイトの目次</a>',
             f'<a class="pg pg-next" href="{nxt[0]}.html"><span>次のページ</span>{esc(nxt[2])}</a>'
             if nxt else '<a class="pg pg-next" href="./"><span>トップへ</span>サイトの目次</a>']
    return f'<nav class="pager" aria-label="前後のページ">{"".join(cells)}</nav>'


def refs_html(docs, extra_md=""):
    items = "".join(f'<li>{doc_credit(d)}</li>' for d in docs)
    extra = md_to_html(extra_md) if extra_md else ""
    n = (items + extra).count("<li")
    cnt = f'<span class="acc-count">{n}件</span>' if n else ""
    return (f'<details class="refs acc" id="references"><summary><h2>出典・参考資料'
            f'{cnt}</h2></summary><div class="acc-body"><ul>{items}</ul>{extra}'
            f'<p class="refs-note">{CREDIT}</p></div></details>')


def jb(text):
    """見出し用：文節の切れ目に <wbr> を入れる（iPhoneのSafariは word-break:auto-phrase 非対応のため）。
    CSS の .jb{word-break:keep-all} と組み合わせ、単語の途中での改行を防ぐ"""
    hira = lambda c: "ぁ" <= c <= "ゖ" or c == "ー"  # noqa: E731
    after_always = set("、。・）」』？！：")
    before_always = set("（「『")
    no_start = set("、。・）」』？！：ーっゃゅょァィゥェォッャュョ")
    particles = set("のをにはがとでへもや")
    out, n = [], len(text)
    for i, c in enumerate(text):
        if i and c in before_always and text[i - 1] not in before_always:
            out.append("\x00")
        out.append(c)
        if i + 1 >= n:
            continue
        nx = text[i + 1]
        if nx in no_start:
            continue
        if c in after_always or (c in particles and i and not hira(text[i - 1]) and not hira(nx)):
            out.append("\x00")
    return '<span class="jb">' + "<wbr>".join(esc(x) for x in "".join(out).split("\x00")) + "</span>"


def h1_lines(seo):
    """見出しは「｜」と途中の「？」で改行する（<title> はそのまま）。
    1行目＝大きな題名、2行目＝シアンの副題、3行目＝灰色の資料名。全角スペース「　」は同じ大きさのまま改行"""
    parts = re.split(r"｜|(?<=？)(?=.)", seo)
    return "<br>".join(f'<span class="h1-line">{"<br>".join(jb(x) for x in s.split("　"))}</span>' for s in parts)


def article_ld(slug, title, desc, keywords, h1, faq_pairs, crumbs, docs):
    url = BASE_URL + f"{slug}.html"
    based = [{"@type": "CreativeWork", "name": DOCS[d]["title"], "url": DOCS[d].get("url", ""),
              "author": {"@type": "Organization", "name": DOCS[d]["org"]},
              **({"license": LICENSE_URL} if LICENSE_URL else {})} for d in docs]
    graph = [
        {"@type": "Article", "@id": url + "#article", "headline": h1[:110], "name": title,
         "description": desc, "url": url, "mainEntityOfPage": url, "inLanguage": "ja",
         "datePublished": PUBLISHED, "dateModified": MODIFIED,
         "author": {"@id": AUTHOR["@id"]}, "publisher": {"@id": PUBLISHER["@id"]},
         "image": BASE_URL + f"ogp/{slug}.png", "keywords": ",".join(keywords),
         "isPartOf": {"@id": BASE_URL + "#website"},
         **({"isBasedOn": based} if based else {}),
         "about": [{"@type": "Thing", "name": n} for n in S.get("about", [])],
         **({"audience": {"@type": "Audience", "audienceType": S["audience"]}} if S.get("audience") else {}),
         "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".lead", ".keypoints", ".answer-first"]}},
        breadcrumb_ld(crumbs), AUTHOR, PUBLISHER,
    ]
    if faq_pairs:
        graph.append({"@type": "FAQPage", "@id": url + "#faq", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a, "url": url + "#" + aid}}
            for q, a, aid in faq_pairs]})
    return {"@context": "https://schema.org", "@graph": graph}


# ------------------------------------------------------------------ 節の描画
SEARCH_DOCS = []
# 「### 職員が確認すること」などの小見出しを、色付きの確認ボックスにする（site.json の roles）
ROLE_NAMES = {r["heading"]: (r.get("cls", "staff"), r.get("icon", "✓"), r.get("label", r["heading"]))
              for r in CFG.get("roles", [])}
ROLE_TAGS = CFG.get("role_tags", {})


def role_class(name):
    """題名の上の「読む人」の札の色：vendor＝緑、exec＝灰、それ以外＝青（判定の語は site.json の role_tags）"""
    for cls in ("vendor", "exec"):
        if ROLE_TAGS.get(cls) and re.search(ROLE_TAGS[cls], name):
            return f"tag-{cls}"
    return "tag-staff"


def genbun_label(name):
    inner = re.sub(r"^原文[（(]?", "", name).rstrip("）)")
    link = ""
    for d, x in DOCS.items():
        if x["title"] in inner and x.get("url"):
            link = f'<a class="genbun-src" href="{x["url"]}" target="_blank" rel="noopener">資料（PDF）を開く</a>'
            break
    return f'<p class="genbun-label"><b>原文引用</b>{esc(inner)}{link}</p>'


def a_red(h):
    """答え（> 答え：）の中の !!…!! で囲んだ部分を赤字にする"""
    return re.sub(r"!!(.+?)!!", r'<span class="a-red">\1</span>', h)


def render_section(slug, page_short, sec_no, sec_title, text, used, faq_pairs):
    sid = f"s{sec_no}"
    question, related, content = pull_meta_lines(text)
    parts, answer, roles = [], "", []
    # AEO用の「答え」：> 答え： 行があればそれ、なければ「ポイント」の箇条を最初の3つまでつなぐ
    # 答えの下に出すボタン：> 答えのボタン：ボタンの文字｜URL
    a_btn = ""
    m_btn = re.search(r"^>\s*答えのボタン[：:]\s*(.+?)[｜|]\s*(https?://\S+)\s*$", content, re.M)
    if m_btn:
        a_btn = (f'<p class="a-btn"><a href="{esc(m_btn.group(2))}" target="_blank" rel="noopener">'
                 f'{esc(m_btn.group(1).strip())} →</a></p>')
        content = content[:m_btn.start()] + content[m_btn.end():]
    m_ans = re.search(r"^>\s*答え[：:]\s*(.+)$", content, re.M)
    if m_ans:
        answer = plain(m_ans.group(1))
        content = content[:m_ans.start()] + content[m_ans.end():]
    else:
        for name, body in split_sub(content):
            if name.startswith("ポイント"):
                items = [plain(ln.lstrip("-* ").strip()) for ln in body.splitlines() if ln.strip().startswith(("-", "*"))]
                answer = "".join(i if i.endswith("。") else i + "。" for i in items[:3])
                break

    def flush_roles():
        if roles:
            parts.append(f'<div class="roles">{"".join(roles)}</div>')
            roles.clear()

    for name, body in split_sub(content):
        if not body:
            continue
        if name in ROLE_NAMES:
            cls, ic, label = ROLE_NAMES[name]
            roles.append(f'<div class="role role-{cls}"><p class="role-h"><span>{ic}</span>{esc(label)}</p>'
                         f'{autolink(md_to_html(body), used)}</div>')
            continue
        flush_roles()
        if name == "":
            parts.append(f'<div class="prose">{autolink(md_to_html(body), used)}</div>')
        elif name.startswith("原文"):
            parts.append(f'<div class="genbun"><button class="genbun-copy" type="button" aria-label="原文をコピー">コピー</button>{genbun_label(name)}'
                         f'<div class="genbun-body">{genbun_html(body)}</div></div>')
        elif name.startswith("解説"):
            if not answer:
                answer = plain(first_paragraphs(body, 1), 300)
            parts.append(voice_html(autolink(md_to_html(body), used)))
        elif name.startswith("図解"):
            cap = name.replace("図解", "").strip("：: ")
            parts.append(f'<figure class="fig">{md_to_html(body)}'
                         f'{f"<figcaption>{esc(cap)}</figcaption>" if cap else ""}</figure>')
        elif name.startswith("資料公表後の動き"):
            parts.append(f'<div class="update"><p class="update-h">資料公表後の動き<small>（引用元の資料より新しい情報。出典は本文中に記載）</small></p>'
                         f'{autolink(md_to_html(body), used)}</div>')
        elif name.startswith("外から確かめる") and CTA:
            parts.append(f'<div class="check-ext"><p class="check-ext-h">🔍 外から確かめる</p>{md_to_html(body)}'
                         f'<p class="check-ext-btn">{cta_link("", esc(CTA["label"]) + "を開く →")}</p></div>')
        elif name.startswith("ポイント"):
            parts.append(f'<div class="points"><p class="points-h">ポイント</p>{autolink(md_to_html(body), used)}</div>')
        elif name.startswith("よくある疑問"):
            qas = re.split(r"^#### ", body, flags=re.M)
            items = []
            for k, qa in enumerate(qas[1:], start=1):
                q, _, a = qa.partition("\n")
                q = re.sub(r"^Q[\.．]\s*", "", q.strip())
                aid = f"{sid}-q{k}"
                items.append(f'<div class="qa" id="{aid}"><p class="qa-q"><span>Q</span>{esc(q)}</p>'
                             f'<div class="qa-a prose"><span class="qa-mark">A</span>{autolink(md_to_html(a.strip()), used)}</div></div>')
                faq_pairs.append((q, plain(a, 500), aid))
            parts.append(f'<div class="qas"><p class="qas-h">よくある疑問</p>{"".join(items)}</div>')
        else:
            parts.append(f'<h3>{esc(name)}</h3><div class="prose">{autolink(md_to_html(body), used)}</div>')
    flush_roles()
    if question:
        faq_pairs.append((question, answer.replace("!!", "") or plain(content, 300), sid))
    qhtml = (f'<div class="qa-box"><p class="q"><span class="q-label">Q</span>{esc(question)}</p>'
             f'{f"<p class=answer-first><span class=a-label>A</span><span>{a_red(esc(answer))}</span></p>" if answer else ""}{a_btn}</div>'
             if question else "")
    rel = (f'<p class="related"><span>関連語</span>{"".join(term_link(w) for w in related)}</p>' if related else "")
    SEARCH_DOCS.append({"p": page_short, "h": f"{sec_no} {sec_title}", "u": f"{slug}.html#{sid}",
                        "q": question or "", "x": plain(content, 1600), "k": " ".join(related)})
    return (f'<section class="sec" id="{sid}" aria-labelledby="{sid}-h">'
            f'<h2 id="{sid}-h"><span class="sno">{sec_no}</span>{jb(sec_title)}'
            f'<a class="anchor" href="#{sid}" aria-label="この節へのリンク">#</a></h2>'
            f'{qhtml}{"".join(parts)}{rel}</section>')


def layout(slug_for_nav, crumbs, top_block, side_toc, article_cls, article_inner):
    top = f'<div class="wrap page-top">{top_block}</div>\n' if top_block else ""
    return f"""{crumb_band(crumbs)}<main id="main" class="page-main">
{top}<div class="wrap layout" id="top">
<aside class="sidebar" aria-label="記事の目次">
  {side_toc}<details class="bn" open><summary>記事の目次</summary>{book_nav(slug_for_nav)}{side_cta()}</details>
</aside>
<div class="main">
<article class="{article_cls}">
{article_inner}
</article>
</div>
</div>
</main>
"""


def page_shell(slug, title, desc, kws, jsonld, crumbs, head_block, body_block, page_type="article", og=None, minfo="",
               top_block="", side_toc=""):
    """top_block：本文の2列の上に全幅で出す見出し部分（章ページ）。side_toc：左の列のいちばん上に出すページ内目次"""
    url = BASE_URL + (f"{slug}.html" if slug else "")
    page = head_html(title, desc, url, kws, og or BASE_URL + f"ogp/{slug}.png", jsonld, page_type)
    page += header_html(slug, breadcrumb_html(crumbs) + minfo)
    inner = f"{head_block}\n{body_block}\n{author_box()}\n{pager(slug) if slug in SLUG_INDEX else ''}"
    page += layout(slug, crumbs, top_block, side_toc, "chapter", inner)
    return page + footer_html()


def render_chapter(p):
    slug, src, short, group, seo, desc, kws = p
    meta, body = read_md(src)
    docs = meta_docs(meta)
    h1, intro_md, secs = split_sections(body)
    title = f"{seo}｜{SITE_NAME}"
    crumbs = [(SITE_NAME, BASE_URL), (group, BASE_URL + f"{slug}.html"), (short, BASE_URL + f"{slug}.html")]
    toc, blocks, faq_pairs, keypoints, refs_extra, used = [], [], [], "", "", set()
    for head, text in secs:
        m = re.match(r"^(\d+)-(\S+)\s+(.*)$", head)
        if not m:
            continue
        sec_no, sec_title = f"{m.group(1)}-{m.group(2)}", m.group(3)
        if m.group(2) == "まとめ":
            _, _, content = pull_meta_lines(text)
            # 番号を付けず、つながった文章にする（長いときだけ項目の切れ目で段落を分ける）
            items = [re.sub(r"^\d+-\d+\s*", "", line.strip()[1:].strip())
                     for line in content.splitlines() if line.strip().startswith("-")]
            paras, cur = [], ""
            for it in items:
                if cur and len(cur) + len(it) > 200:
                    paras.append(cur)
                    cur = ""
                cur += it
            if cur:
                paras.append(cur)
            keypoints = (f'<section class="keypoints" aria-labelledby="kp"><h2 id="kp"><span class="kp-chip">SUMMARY</span>このページの要点</h2>'
                         + "".join("<p>" + re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t)) + "</p>" for t in paras) + '</section>')
            continue
        if m.group(2) == "参考":
            _, _, refs_extra = pull_meta_lines(text)
            continue
        toc.append(f'<li><a href="#s{sec_no}"><span class="tno">{sec_no}</span>{jb(sec_title)}</a></li>')
        blocks.append(render_section(slug, short, sec_no, sec_title, text, used, faq_pairs))
    CH_QUESTIONS.update(q for q, _, _ in faq_pairs)
    jsonld = article_ld(slug, title, desc, kws, seo, faq_pairs, crumbs, docs)
    lead = lead_html(first_paragraphs(intro_md, 1)) if intro_md else esc(desc)
    intro_cta = "".join(re.findall(r'<div class="app-cta">.*?</div>', intro_md or "", flags=re.S))
    chips = "".join(f'<span class="tag {role_class(r.strip())}">{esc(r.strip())}</span>'
                    for r in meta.get("actors", "").strip("[]").split(",") if r.strip())
    where = meta.get("where", "")
    meta_row = (f'<div class="chapter-meta">'
                f'{f"<span class=tag-season>原文の場所：{esc(where)}</span>" if where else ""}'
                f'{chips}</div>') if (where or chips) else ""
    toc_html = (f'<nav class="toc toc-body" aria-label="このページの目次"><p class="toc-title">このページの目次</p><ol>{"".join(toc)}</ol></nav>'
                if len(toc) > 1 else "")
    side_toc = (f'<nav class="toc toc-side" id="page-toc" aria-label="このページの目次（左の列）"><p class="toc-title">'
                f'<span>このページの目次</span><small>全{len(toc)}節</small></p><ol>{"".join(toc)}</ol></nav>'
                if len(toc) > 1 else "")
    h1_html = f"<h1>{h1_lines(seo)}</h1>"
    if meta.get("hero"):
        # 題名の横に専用の画像を出すページ（hero: 画像|代替テキスト|リンク先）。共通の横長の帯は出さない
        isrc, alt, href = (meta["hero"].split("|") + ["", ""])[:3]
        img = f'<img src="{esc(isrc)}" alt="{esc(alt)}" width="640" height="360" loading="lazy" decoding="async">'
        img = f'<a class="h1-img" href="{esc(href)}">{img}</a>' if href else f'<span class="h1-img">{img}</span>'
        h1_html = f'<div class="h1-row">{h1_html}{img}</div>'
    top_block = f"""<header class="chapter-head">
  <p class="chapter-no">{esc(group)}<span class="chapter-title">{esc(short)}</span></p>
  {meta_row}
  {h1_html}
  <p class="lead">{lead}</p>
  {"" if meta.get("hero") else page_hero(group, short)}
  {author_bar(docs, toc=bool(toc_html))}
</header>"""
    head_block = f"{intro_cta}\n{keypoints}\n{toc_html}"
    refs = refs_html(docs, refs_extra) if (docs or refs_extra) else ""
    body_html, refs = link_ref_numbers("".join(blocks), refs)
    return page_shell(slug, title, desc, kws, jsonld, crumbs, head_block, body_html + refs, minfo=meta_row,
                      top_block=top_block, side_toc=side_toc)


def link_ref_numbers(body_html, refs):
    """参考資料の「［n］…」項目に id="ref-n" を付け、本文中の［n］［n・m］［n〜m］を各項目へのリンクにする"""
    refs = re.sub(r"<li>［(\d+)］", r'<li id="ref-\1">［\1］', refs)
    ids = set(re.findall(r'id="ref-(\d+)"', refs))
    if not ids:
        return body_html, refs

    def one(n):
        return f'<a class="ref-link" href="#ref-{n}">{n}</a>' if n in ids else n

    def rep(m):
        inner = re.sub(r"\d+", lambda x: one(x.group(0)), m.group(1))
        return f"［{inner}］"
    parts = re.split(r"(<[^>]+>)", body_html)
    out = [p if p.startswith("<") else re.sub(r"［([\d・〜～,，\s]+)］", rep, p) for p in parts]
    return "".join(out), refs


# ------------------------------------------------------------------ 用語集ページ
GYO = [("あ", "あいうえおぁぃぅぇぉ"), ("か", "かきくけこがぎぐげご"), ("さ", "さしすせそざじずぜぞ"),
       ("た", "たちつてとだぢづでどっ"), ("な", "なにぬねの"), ("は", "はひふへほばびぶべぼぱぴぷぺぽ"),
       ("ま", "まみむめも"), ("や", "やゆよゃゅょ"), ("ら", "らりるれろ"), ("わ", "わをん")]


def gyo_of(reading, term=""):
    if re.match(r"[A-Za-z0-9]", term):
        return "英数"
    c = reading[:1]
    for g, chars in GYO:
        if c in chars:
            return g
    return "英数"


def chapter_texts():
    """用語の「本文で読む」に使う本文の節（用語集と、原稿ファイル名が 9 で始まる付録は除く）"""
    out = []
    for p in PAGES:
        if p[0] == G_SLUG or p[1].startswith("9"):
            continue
        _, body = read_md(p[1])
        _, _, secs = split_sections(body)
        for head, text in secs:
            m = re.match(r"^(\d+-\d+)\s+(.*)$", head)
            if m:
                out.append((p, m.group(1), m.group(2), text))
    return out


def render_glossary(p):
    slug, src, short, group, seo, desc, kws = p
    meta, body = read_md(src)
    h1, intro_md, secs = split_sections(body)
    title = f"{seo}｜{SITE_NAME}"
    url = BASE_URL + f"{slug}.html"
    crumbs = [(SITE_NAME, BASE_URL), (short, url)]
    corpus = chapter_texts()
    by_gyo, entries, terms_ld = {}, [], []
    for head, text in sorted_terms(secs):
        m = TERM_HEAD.match(head)
        if not m:
            continue
        term, reading = m.group(1).strip(), m.group(2).strip()
        g = gyo_of(reading, term)
        by_gyo.setdefault(g, []).append(term)
        question, related, content = pull_meta_lines(text)
        seen, appear = set(), []
        for cp, sno, stitle, stext in corpus:
            if cp[0] in seen or term not in stext:
                continue
            seen.add(cp[0])
            appear.append(f'<a href="{cp[0]}.html#s{sno}">{esc(cp[2])}（{sno}）</a>')
            if len(appear) >= 3:
                break
        rel = (f'<p class="related"><span>関連語</span>{"".join(term_link(w) for w in related)}</p>' if related else "")
        app = (f'<p class="appear"><span>本文で読む</span>{"".join(appear)}</p>' if appear else "")
        short_def = plain(first_paragraphs(content, 1), 170)
        entries.append(
            f'<section class="term" id="{TERMS[term]["slug"]}" data-gyo="{g}"><h2><a class="term-name" href="{term_url(term)}">{esc(term)}</a>'
            f'<span class="reading">{esc(reading)}</span></h2><p class="term-def">{esc(short_def)}</p>'
            f'<p class="term-more"><a href="{term_url(term)}">{esc(term)}とは？意味・資料での使われ方を詳しく見る →</a></p>{rel}{app}</section>')
        terms_ld.append({"@type": "DefinedTerm", "name": term, "alternateName": reading,
                         "description": plain(first_paragraphs(content, 1), 300),
                         "url": BASE_URL + term_url(term), "inDefinedTermSet": url + "#terms"})
    order = ["英数"] + [g for g, _ in GYO]
    index_nav = "".join(f'<a href="#g-{g}">{g}</a>' for g in order if g in by_gyo)
    index_lists = "".join(
        f'<div class="gyo" id="g-{g}"><p class="gyo-h">{g}</p><ul>'
        + "".join(f'<li><a href="{term_url(t)}">{esc(t)}</a></li>' for t in by_gyo[g]) + "</ul></div>"
        for g in order if g in by_gyo)
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "DefinedTermSet", "@id": url + "#terms", "name": GLOSSARY_NAME, "url": url,
         "description": desc, "inLanguage": "ja", "hasDefinedTerm": terms_ld},
        {"@type": "WebPage", "@id": url, "url": url, "name": title, "description": desc, "inLanguage": "ja",
         "datePublished": PUBLISHED, "dateModified": MODIFIED, "author": {"@id": AUTHOR["@id"]},
         "isPartOf": {"@id": BASE_URL + "#website"}},
        breadcrumb_ld(crumbs), AUTHOR, PUBLISHER]}
    head_block = f"""<header class="chapter-head">
  <p class="chapter-no">{esc(group)}<span class="chapter-title">{esc(short)}</span></p>
  <h1>{h1_lines(seo)}</h1>
  <p class="lead">{esc(plain(intro_md))}</p>
  {byline()}
</header>
<nav class="gyo-nav" aria-label="五十音で探す">{index_nav}</nav>
<div class="term-index">{index_lists}</div>"""
    return page_shell(slug, title, desc, kws, jsonld, crumbs, head_block, "".join(entries), "website")


def term_paragraph(text, term):
    _, _, content = pull_meta_lines(text)
    for name, body in split_sub(content):
        if name.startswith("図解"):
            continue
        for para in re.split(r"\n\s*\n", body):
            if term in para and not para.lstrip().startswith(("-", "|", "#", "<")):
                return plain(para, 150), name.startswith("原文")
    return "", False


def term_owners():
    """「〇〇とは」を担当する本文ページ（キーワードかSEOタイトルの先頭が「〇〇とは」）"""
    own = {}
    for p in PAGES:
        if p[0] == G_SLUG:
            continue
        heads = [k.replace(" ", "") for k in p[6]] + [p[4].split("？")[0].replace(" ", "")]
        for h in heads:
            m = re.match(r"^(.+?)とは$", h)
            if m and m.group(1) not in own:
                own[m.group(1)] = (f"{p[0]}.html", p[2])
    return own


def render_term(term, prev_t, next_t, corpus):
    info = TERMS[term]
    question, related, content = pull_meta_lines(info["text"])
    reading = info["reading"]
    url = BASE_URL + term_url(term)
    owner = OWNERS.get(term.replace(" ", ""))
    definition = plain(first_paragraphs(content, 1))
    gname = GLOSSARY_NAME
    if owner:
        # 「〇〇とは」は本文ページが担当。用語ページは「意味（一言で）」の検索を担当して重複を避ける
        title = f"{term}の意味を一言で｜{gname}"
        desc = plain(f"{term}の意味を短く解説。" + first_paragraphs(content, 1), 118)
        kws = [f"{term} 意味", f"{term} 用語", f"{term} 定義", f"{term} 一言で"]
        q_name = f"{term}の意味は？"
        owner_box = (f'<p class="owner-link"><b>詳しい解説：</b><a href="{owner[0]}">{esc(owner[1])}</a>'
                     f'で、{esc(term)}を原文と解説でくわしく読めます。</p>')
    else:
        title = f"{term}とは？意味をわかりやすく解説｜{gname}"
        desc = plain(first_paragraphs(content, 1), 118)
        kws = [f"{term}とは", f"{term} 意味", f"{term} わかりやすく"]
        q_name = f"{term}とは何ですか？"
        owner_box = ""
    if q_name in CH_QUESTIONS:
        q_name = f"{term}の意味は？"
    used = {k.replace(" ", "") for p in PAGES for k in p[6]}
    kws = [k for k in kws if k.replace(" ", "") not in used] or kws[:1]
    rel_cards = []
    for w in related:
        if w in TERMS and w != term:
            _, _, wc = pull_meta_lines(TERMS[w]["text"])
            rel_cards.append(f'<li><a href="{term_url(w)}"><b>{esc(w)}</b><span>{esc(plain(first_paragraphs(wc, 1), 70))}</span></a></li>')
    appear, seen = [], set()
    for cp, sno, stitle, stext in corpus:
        if cp[0] in seen or term not in stext:
            continue
        excerpt, is_gen = term_paragraph(stext, term)
        if not excerpt:
            continue
        seen.add(cp[0])
        appear.append(f'<li><a href="{cp[0]}.html#s{sno}"><span class="ap-ch">{esc(cp[2])}　{sno}{"（原文）" if is_gen else ""}</span>'
                      f'<b>{esc(stitle)}</b><span class="ap-ex">{esc(excerpt)}</span></a></li>')
        if len(appear) >= 5:
            break
    gpage = PAGES[SLUG_INDEX[G_SLUG]]
    crumbs = [(SITE_NAME, BASE_URL), (gpage[2], BASE_URL + f"{G_SLUG}.html"), (term, url)]
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "DefinedTerm", "@id": url + "#term", "name": term, "alternateName": reading,
         "description": definition[:500], "url": url,
         "inDefinedTermSet": {"@type": "DefinedTermSet", "@id": BASE_URL + f"{G_SLUG}.html#terms",
                              "name": gname, "url": BASE_URL + f"{G_SLUG}.html"}},
        {"@type": "WebPage", "@id": url, "url": url, "name": title, "description": desc, "inLanguage": "ja",
         "datePublished": PUBLISHED, "dateModified": MODIFIED, "author": {"@id": AUTHOR["@id"]},
         "publisher": {"@id": PUBLISHER["@id"]}, "isPartOf": {"@id": BASE_URL + "#website"},
         "about": {"@id": url + "#term"}, "keywords": ",".join(kws)},
        {"@type": "FAQPage", "@id": url + "#faq", "mainEntity": [
            {"@type": "Question", "name": q_name,
             "acceptedAnswer": {"@type": "Answer", "text": definition[:600], "url": url}}]},
        breadcrumb_ld(crumbs), AUTHOR, PUBLISHER]}
    nav = (f'<nav class="pager" aria-label="前後の用語">'
           f'<a class="pg pg-prev" href="{term_url(prev_t)}"><span>前の用語</span>{esc(prev_t)}</a>'
           f'<a class="pg pg-next" href="{term_url(next_t)}"><span>次の用語</span>{esc(next_t)}</a></nav>')
    SEARCH_DOCS.append({"p": gpage[2], "h": term, "u": term_url(term), "q": f"{term}とは", "x": plain(content, 600),
                        "k": reading + " " + " ".join(related)})
    page = head_html(title, desc, url, kws, BASE_URL + f"ogp/{G_SLUG}.png", jsonld)
    page += header_html(G_SLUG, breadcrumb_html(crumbs))
    inner = f"""<header class="chapter-head">
  <p class="chapter-no">{esc(gpage[2])}<span class="chapter-title">{esc(GLOSSARY.get("kicker", "キーワード"))}</span></p>
  <h1>{esc(term)}{"の意味" if owner else "とは"}<span class="h1-reading">{esc(reading)}</span></h1>
  {byline()}
</header>
{owner_box}
<section class="definition" aria-labelledby="def-h">
  <h2 id="def-h">{esc(term)}の意味</h2>
  {voice_html(autolink(md_to_html(content), set(), limit=4, exclude={term}))}
</section>
{f'<section class="term-sec"><h2>関連する用語</h2><ul class="rel-cards">{"".join(rel_cards)}</ul></section>' if rel_cards else ""}
{f'<section class="term-sec"><h2>このサイトの本文で{esc(term)}を読む</h2><ul class="appear-list">{"".join(appear)}</ul></section>' if appear else ""}
{cta_buttons("cta-btns cta-inline")}
<p class="back-glossary"><a href="{G_SLUG}.html">{esc(gpage[2])}の一覧に戻る</a></p>
{nav}
{author_box()}"""
    page += layout(G_SLUG, crumbs, "", "", "chapter term-page", inner)
    return page + footer_html()


# ------------------------------------------------------------------ 検索ページ
def render_search():
    sc = CFG.get("search", {})
    title = f"サイト内検索｜{SITE_NAME}"
    desc = sc.get("desc", f"{SITE_NAME}の原文・解説・用語集をキーワードで検索できます。")
    url = BASE_URL + "search.html"
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "SearchResultsPage", "@id": url, "url": url, "name": title, "inLanguage": "ja",
         "isPartOf": {"@id": BASE_URL + "#website"}}]}
    page = head_html(title, desc, url, [f"{SITE_NAME} 検索"], BASE_URL + "ogp/index.png", jsonld, "website",
                     robots="noindex,follow")
    page += header_html("search")
    crumbs = [(SITE_NAME, BASE_URL), ("サイト内検索", url)]
    inner = f"""<header class="chapter-head">
  <p class="chapter-no">検索<span class="chapter-title">原文・解説・用語集</span></p>
  <h1>サイト内検索</h1>
  <form class="big-search" action="search.html" method="get" role="search">
    <input type="search" name="q" id="pq" placeholder="{esc(sc.get('placeholder', 'キーワードを入力'))}" aria-label="検索語">
    <button type="submit">検索</button>
  </form>
  <p class="search-tips">{esc(sc.get('tips', 'スペースで区切ると、すべての語を含む節を探します。'))}</p>
</header>
<div id="search-page-results" aria-live="polite"></div>"""
    page += layout("", crumbs, "", "", "chapter", inner)
    return page + footer_html()


# ------------------------------------------------------------------ トップページ
def render_index():
    H = CFG["home"]
    title, desc, kws = H["title"], H["desc"], H.get("keywords", [])
    url = BASE_URL
    cards = []
    for g in GROUP_ORDER:
        items = [f'<li><a class="card" href="{p[0]}.html"><span class="card-no">{esc(p[3])}</span>'
                 f'<span class="card-title">{jb(p[2])}</span><span class="card-desc">{esc(p[5][:76])}…</span></a></li>'
                 for p in PAGES if p[3] == g]
        if items:
            cards.append(f'<section class="group"><h3>{esc(g)}</h3><ul class="cards">{"".join(items)}</ul></section>')
    popular = "".join(
        f'<li><a href="{term_url(w)}"><b>{esc(w)}</b><span>{esc(plain(first_paragraphs(pull_meta_lines(TERMS[w]["text"])[2], 1), 46))}</span></a></li>'
        for w in list(TERMS)[:18])
    docs = "".join(
        f'<li><a href="{esc(c["slug"])}.html"><span class="doc-org">{esc(c["org"])}<small>{esc(c.get("date", ""))}</small></span>'
        f'<b>{esc(c["title"])}</b><span class="doc-what">{esc(c.get("text", ""))}</span><span class="doc-go">{esc(group_of(c["slug"]) or "")}を読む →</span></a></li>'
        for c in H.get("doc_cards", []) if c["slug"] in SLUG_INDEX)
    points = H.get("points", [])
    seo_points = "".join(
        f'<article class="seo-point"><h3>{esc(x["q"])}</h3><p>{esc(x["a"])}</p><p class="seo-links">'
        + "".join(f'<a href="{esc(l["href"])}">{esc(l["label"])}</a>' for l in x.get("links", [])) + '</p></article>'
        for x in points)
    who = "".join(f'<li class="t-{"abc"[i % 3]}"><a href="{esc(w["href"])}"><b>{esc(w["label"])}</b><span>{esc(w["text"])}</span></a></li>'
                  for i, w in enumerate(H.get("who", [])))
    buttons = "".join(f'<a class="btn{" btn-primary" if b.get("primary") else ""}" href="{esc(b["href"])}">{esc(b["label"])}</a>'
                      for b in H.get("buttons", []))
    img = ""
    if H.get("image"):
        base, ext = H["image"].rsplit(".", 1)
        webp = f'<source srcset="{esc(base)}.webp" type="image/webp">' if (ROOT / f"{base}.webp").exists() and ext != "webp" else ""
        img = (f'<picture class="hero-img">{webp}<img src="{esc(H["image"])}" alt="{esc(H.get("image_alt", ""))}" '
               f'width="960" height="960" fetchpriority="high"></picture>')
    jump = [("h-docs", "資料"), ("h-toc", "記事の目次")] if docs else [("h-toc", "記事の目次")]
    if TERMS:
        jump.append(("h-terms", "用語"))
    if who:
        jump.append(("h-who", "読む人別"))
    if seo_points:
        jump.append(("h-seo", "要点"))
    faq = [{"@type": "Question", "name": x["q"], "acceptedAnswer": {"@type": "Answer", "text": x["a"]}} for x in points]
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": BASE_URL + "#website", "url": BASE_URL, "name": SITE_NAME,
         "alternateName": SITE_FULL, "description": desc, "inLanguage": "ja", "publisher": {"@id": PUBLISHER["@id"]},
         "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": BASE_URL + "search.html?q={search_term_string}"},
                             "query-input": "required name=search_term_string"}},
        {"@type": "WebPage", "@id": BASE_URL + "#webpage", "url": BASE_URL, "name": title, "description": desc,
         "inLanguage": "ja", "isPartOf": {"@id": BASE_URL + "#website"}, "author": {"@id": AUTHOR["@id"]},
         "datePublished": PUBLISHED, "dateModified": MODIFIED, "primaryImageOfPage": BASE_URL + "ogp/index.png",
         "isBasedOn": [{"@type": "CreativeWork", "name": DOCS[d]["title"], "url": DOCS[d].get("url", ""),
                        "author": {"@type": "Organization", "name": DOCS[d]["org"]}} for d in MAIN_DOCS]},
        {"@type": "ItemList", "name": "目次", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": p[2], "url": BASE_URL + f"{p[0]}.html"} for i, p in enumerate(PAGES)]},
        *([{"@type": "FAQPage", "@id": BASE_URL + "#faq", "mainEntity": faq}] if faq else []),
        AUTHOR, PUBLISHER]}
    page = head_html(title, desc, url, kws, BASE_URL + "ogp/index.png", jsonld, "website")
    page += header_html()
    h1_sub = f'<span class="h1-sub">{esc(H["h1_sub"])}</span>' if H.get("h1_sub") else ""
    page += f"""<main id="main" class="home">
<section class="hero" id="top">
  <div class="wrap hero-inner"><div class="hero-main"><div class="hero-text">
    <p class="eyebrow">{esc(H.get("eyebrow", ""))}</p>
    <h1><span class="h1-main">{H["h1"]}</span>{h1_sub}</h1>
    <p class="hero-lead">{H.get("lead", "")}</p>
    <button class="lead-more" type="button" aria-expanded="false">続きを読む</button>
    </div>{img}
    </div><div class="hero-side"><form class="big-search" action="search.html" method="get" role="search">
      <input type="search" name="q" class="js-search" placeholder="{esc(CFG.get('search', {}).get('placeholder', 'キーワードを入力'))}" aria-label="サイト内検索">
      <button type="submit">検索</button>
      <div class="sresults" hidden></div>
    </form>
    <div class="hero-cta">{buttons}</div>
    <nav class="home-jump" aria-label="このページの中の案内">{"".join(f'<a href="#{i}">{t}</a>' for i, t in jump)}</nav>
    {cta_buttons()}
    {byline()}</div>
  </div>
</section>
<div class="wrap home-body">
{f'''<section class="block" aria-labelledby="h-seo">
  <h2 id="h-seo">{esc(H.get("points_title", "要点"))}</h2>
  <div class="seo-points">{seo_points}</div>
</section>''' if seo_points else ""}
{f'''<section class="block" aria-labelledby="h-who">
  <h2 id="h-who">読む人別の入口</h2>
  <ul class="three who">{who}</ul>
</section>''' if who else ""}
{f'''<section class="block" aria-labelledby="h-docs">
  <h2 id="h-docs">このサイトで読める資料</h2>
  <ul class="doc-cards">{docs}</ul>
</section>''' if docs else ""}
<section class="block" aria-labelledby="h-toc">
  <h2 id="h-toc">目次</h2>
  {"".join(cards)}
</section>
{f'''<section class="block" aria-labelledby="h-terms">
  <h2 id="h-terms">よく調べられる用語</h2>
  <ul class="popular-terms">{popular}</ul>
  <p><a class="more" href="{G_SLUG}.html">用語集をすべて見る →</a></p>
</section>''' if TERMS else ""}
<section class="block">
  <details class="note site-about"><summary>このサイトについて（出典・利用規約）</summary><div class="site-about-body">{CREDIT}</div></details>
  {author_box()}
</section>
</div>
</main>
"""
    return page + footer_html()


# ------------------------------------------------------------------ sitemap / llms.txt / 検索インデックス
def write_sitemap():
    urls = ([(BASE_URL, "1.0")] + [(BASE_URL + f"{p[0]}.html", "0.8") for p in PAGES]
            + [(BASE_URL + term_url(w), "0.6") for w in TERMS])
    body = "".join(f"<url><loc>{u}</loc><lastmod>{MODIFIED}</lastmod><priority>{pr}</priority></url>" for u, pr in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n',
        encoding="utf-8")


def write_llms():
    appendix = GROUP_ORDER[-1]
    lines = [f"# {SITE_FULL}", "", f"> {CFG.get('llms_intro', SITE_SUB)}", "",
             f"解説の著者：{A['name']}（{A.get('title', '')}）。{A.get('bio', '')}",
             "原文の出典：" + "／".join(f"{doc_name(d)} {DOCS[d].get('url', '')}" for d in MAIN_DOCS)
             + (f"（{LICENSE_NAME}）。" if LICENSE_NAME else "。"),
             "原文は「### 原文」見出しの下、解説は「### 解説」見出しの下にあります。"
             "資料の内容として引用するときは「原文」部分を、説明として使うときは「解説」部分を使ってください。",
             "", "## 本文"]
    lines += [f"- [{p[2]}]({BASE_URL}{p[0]}.html): {p[5]}" for p in PAGES if p[3] != appendix]
    lines += ["", "## 付録"] + [f"- [{p[2]}]({BASE_URL}{p[0]}.html): {p[5]}" for p in PAGES if p[3] == appendix]
    if TERMS:
        lines += ["", "## 用語の個別ページ"]
        for w in TERMS:
            _, _, wc = pull_meta_lines(TERMS[w]["text"])
            lines.append(f"- [{w}とは]({BASE_URL}{term_url(w)}): {plain(first_paragraphs(wc, 1), 80)}")
    lines += ["", "## Optional", f"- [全文テキスト]({BASE_URL}llms-full.txt): 全ページの原文と解説（Markdown）"]
    (ROOT / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    full = [f"# {SITE_FULL}", "", f"サイトURL：{BASE_URL}", "原文出典：" + "／".join(DOCS[d].get("url", "") for d in MAIN_DOCS),
            f"解説：{A['name']}", ""]
    for p in PAGES:
        _, body = read_md(p[1])
        full.append(f"\n\n<!-- {BASE_URL}{p[0]}.html -->\n")
        full.append(re.sub(r"!!(.+?)!!", r"**\1**", re.sub(r"<svg[\s\S]*?</svg>", "（図）", body.strip())))
    (ROOT / "llms-full.txt").write_text("\n".join(full) + "\n", encoding="utf-8")


def write_search_index():
    syn = []
    f = SRC / "_同義語.txt"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                syn.append([w.strip() for w in re.split(r"[,、，=＝]", line) if w.strip()])
    (ROOT / "search-index.json").write_text(
        json.dumps({"docs": SEARCH_DOCS, "syn": syn}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# ------------------------------------------------------------------ OGP画像・アイコン（Stitch の濃紺×シアン）
FONT_CANDIDATES = {
    "bold": ["C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryob.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"],
    "regular": ["C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/meiryo.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"],
}


def find_font(kind):
    custom = S.get("ogp_font_" + kind)
    for f in ([custom] if custom else []) + FONT_CANDIDATES[kind]:
        if f and Path(f).exists():
            return f
    return None


def write_images():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  [注意] Pillow が無いので OGP画像・アイコンを作りませんでした（pip install pillow）")
        return
    fb, fr = find_font("bold"), find_font("regular")
    if not (fb and fr):
        print("  [注意] 日本語フォントが見つからないので OGP画像を作りませんでした（site.json の ogp_font_bold / ogp_font_regular で指定）")
        return
    out = ROOT / "ogp"
    out.mkdir(exist_ok=True)
    navy, cyan, white, sub = (11, 25, 44), (34, 211, 238), (255, 255, 255), (186, 200, 220)

    def wrap(draw, text, font, width):
        lines, cur = [], ""
        for ch in text:
            if draw.textlength(cur + ch, font=font) > width:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    def make(name, label, title, subt=""):
        im = Image.new("RGB", (1200, 630), navy)
        d = ImageDraw.Draw(im)
        for x in range(0, 1200, 40):
            d.line([x, 0, x, 630], fill=(20, 36, 58))
        for y in range(0, 630, 40):
            d.line([0, y, 1200, y], fill=(20, 36, 58))
        d.rectangle([0, 0, 1200, 10], fill=cyan)
        f_site, f_label = ImageFont.truetype(fr, 30), ImageFont.truetype(fb, 30)
        d.text((90, 64), SITE_NAME, font=f_site, fill=sub)
        if label:
            label = label if len(label) <= 30 else label[:29] + "…"
            d.rounded_rectangle([90, 140, 90 + d.textlength(label, font=f_label) + 40, 192], 8, fill=(14, 116, 144))
            d.text((110, 146), label, font=f_label, fill=white)
        size = 64 if len(title) <= 28 else 54
        f_title = ImageFont.truetype(fb, size)
        y = 236
        for line in [ln for part in title.split("　") for ln in wrap(d, part, f_title, 1020)][:3]:
            d.text((90, y), line, font=f_title, fill=white)
            y += int(size * 1.4)
        if subt:
            f_sub = ImageFont.truetype(fr, 32)
            y += 8
            for line in [ln for part in subt.split("｜") for ln in wrap(d, part, f_sub, 1020)][:2]:
                d.text((90, y), line, font=f_sub, fill=cyan)
                y += 48
        d.line([90, 548, 1110, 548], fill=(40, 60, 88), width=2)
        d.text((90, 564), f"解説：{A['name']}", font=f_site, fill=sub)
        im.save(out / f"{name}.png", optimize=True)

    H = CFG["home"]
    make("index", S.get("ogp_label", ""), re.sub(r"<[^>]+>", "", H["h1"]), SITE_SUB)
    for p in PAGES:
        main_t, _, sub_t = p[4].partition("｜")
        make(p[0], p[3], main_t, sub_t)

    logo = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(logo)
    d.rounded_rectangle([0, 0, 512, 512], 96, fill=navy)
    d.rectangle([0, 404, 512, 420], fill=cyan)
    f = ImageFont.truetype(fb, 300)
    ch = S.get("logo_char", SITE_NAME[:1])
    w = d.textlength(ch, font=f)
    d.text(((512 - w) / 2, 40), ch, font=f, fill=white)
    logo.save(out / "logo.png", optimize=True)
    logo.resize((180, 180)).save(ROOT / "apple-touch-icon.png")
    logo.resize((32, 32)).save(ROOT / "favicon-32.png")
    logo.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


# ------------------------------------------------------------------ 実行
ASSET_VER = ""


def main():
    global ASSET_VER, AUTO_RE, OWNERS
    assemble()
    load_terms()
    if TERMS:
        auto = sorted((w for w in TERMS if len(w) >= 3), key=len, reverse=True)
        AUTO_RE = re.compile("|".join(re.escape(w) for w in auto)) if auto else None
    ASSET_VER = asset_ver()
    for p in PAGES:
        html_text = render_glossary(p) if p[0] == G_SLUG else render_chapter(p)
        (ROOT / f"{p[0]}.html").write_text(html_text, encoding="utf-8")
    OWNERS = term_owners()
    corpus = chapter_texts()
    names = list(TERMS)
    for i, w in enumerate(names):
        (ROOT / term_url(w)).write_text(render_term(w, names[i - 1], names[(i + 1) % len(names)], corpus), encoding="utf-8")
    (ROOT / "index.html").write_text(render_index(), encoding="utf-8")
    (ROOT / "search.html").write_text(render_search(), encoding="utf-8")
    write_search_index()
    write_sitemap()
    write_llms()
    write_images()
    print("built", len(PAGES) + 2, "pages +", len(TERMS), "term pages,", len(SEARCH_DOCS), "search docs")


if __name__ == "__main__":
    sys.exit(main())
