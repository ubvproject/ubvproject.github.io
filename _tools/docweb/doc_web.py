"""Веб-версия справки UBV-AS-2026-01 в стиле UbV (светлая и тёмная тема, анимации).

ТЕКСТ НЕ МЕНЯЕТСЯ: всё берётся из опубликованного PDF (pdftohtml -xml), склейка строк только снимает
автоматические переносы (U+2010). Схемы и скриншоты — вырезка из страниц PDF. В конце — сверка всех слов
с PDF (difflib), расхождения печатаются.

python3 src/doc_web.py  ->  site_proto/ubv-as-2026-01.html + site_proto/assets/doc/*.jpg
"""
import difflib
import html
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdfxml as X  # noqa: E402

PDF = OUT = ADIR = TMP = None
META = {}


def configure(pdf, out_dir, tmp_dir, meta=None):
    """pdf — исходник; out_dir — папка документа на сайте (index.html + fig/); tmp_dir — кэш разбора."""
    global PDF, OUT, ADIR, TMP, META, _SOFT_PAIRS
    PDF, OUT, TMP = pdf, out_dir, tmp_dir
    ADIR = os.path.join(out_dir, "fig")
    META = meta or {}
    _SOFT_PAIRS = None
SCALE = 2          # растр 216 dpi -> 2 px на единицу XML (XML = pt × 1.5)
GREEN = "#2e593f"
SOFT = "‐"


def esc(s):
    return html.escape(s, quote=False)


# ------------------------------------------------------------------ подготовка
def prepare():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(ADIR, exist_ok=True)
    xml = os.path.join(TMP, "as.xml")
    stamp = os.path.join(TMP, "source.txt")
    src_id = f"{os.path.getsize(PDF)}:{os.path.getmtime(PDF)}"
    if not os.path.exists(stamp) or open(stamp).read() != src_id:      # новая редакция PDF -> разобрать заново
        for f in os.listdir(TMP):
            os.remove(os.path.join(TMP, f))
        subprocess.run(["pdftohtml", "-xml", "-i", "-q", PDF, os.path.join(TMP, "as")], check=True)
        subprocess.run(["pdftoppm", "-r", "216", "-png", PDF, os.path.join(TMP, "p")], check=True)
        open(stamp, "w").write(src_id)
    return X.load(xml)


def page_png(pno):
    return os.path.join(TMP, f"p-{pno:02d}.png")


# ------------------------------------------------------------------ роли строк
def role(ln):
    size, fam, col, bold, ital = ln.main()
    t = ln.text.strip()
    first = ln.segs[0]
    if ln.top < 75:
        return "header"
    if ln.top > 1175 and re.fullmatch(r"\d+", t):
        return "pageno"
    if fam.startswith("PTSans") and size == 24 and bold:
        return "h1"
    if fam.startswith("PTSans") and size == 18 and bold:
        return "h2"
    if first.color == GREEN and first.bold and re.match(r"Б\s*\d+\.\d+", t) and fam.startswith("PTSans") and size == 14:
        return "q"
    if fam.startswith("PTSans") and size == 14 and bold and col == "#111111":
        return "qcont_or_h3"
    if fam.startswith("PTSans") and size == 14 and not bold and t.startswith("Таблица"):
        return "tcap"
    if fam.startswith("PTSans") and size == 13 and col == "#333333" and t.startswith("Рисунок"):
        return "fcap"
    if fam.startswith("PTSerif") and size == 16:
        return "body"
    if fam.startswith("PTSerif") and size == 13:
        return "body_s"
    if fam.startswith("PTSans") and size == 12 and col == "#6a6a6a":
        return "note"
    if fam.startswith("PTSans") and size == 11 and col == "#333333":
        return "foot"
    if fam.startswith("PTSans") and size in (12, 13) and col in ("#111111", "#333333"):
        return "cell"
    if fam.startswith("PTMono") and size in (10, 11, 12, 14):
        return "cell"
    if fam.startswith("PTSans") and size == 10 and col == "#6a6a6a":
        return "cell"
    if fam.startswith("PTSans") and size == 13 and col == "#666666":
        return "foot"
    return "fig"


def attach_superscripts(lines):
    """Цифры сносок (PTMono ≤ 9) — отдельные «строки»; прикрепляем к строке, в которую они попадают."""
    keep = []
    for ln in lines:
        s = ln.segs
        if len(s) == 1 and s[0].family.startswith("PTMono") and s[0].size <= 9 and s[0].text.strip().isdigit():
            host = next((o for o in lines if o is not ln and o.top - 6 <= s[0].top <= o.bottom and o.left <= s[0].left <= o.right + 4), None)
            if host:
                s[0].sup = True
                host.segs.append(s[0])
                host.segs.sort(key=lambda q: q.left)
                continue
        keep.append(ln)
    return keep


# ------------------------------------------------------------------ склейка текста
def seg_html(s, links=True):
    t = s.text
    if getattr(s, "sup", False):
        n = t.strip()
        return f'<sup class="fnref"><a href="#fn-{n}" id="fnref-{n}">{n}</a></sup>'
    out = esc(t)
    if s.family.startswith("PTMono"):
        out = f"<code>{out}</code>"
    elif s.color == GREEN and s.bold and re.fullmatch(r"\s*Б?\d+(\.\d+)?\s*", t) is None and False:
        pass
    if s.bold and not s.family.startswith("PTMono") and s.color != GREEN:
        out = f"<b>{out}</b>"
    if s.italic:
        out = f"<i>{out}</i>"
    return out


def line_parts(ln):
    """[(html, plain)] сегментов строки с пробелами по зазорам. Отдельный сегмент «-» в конце строки —
    автоматический перенос Chrome (у настоящих дефисов «-» стоит внутри слова) -> помечаем U+2010."""
    parts = []
    prev = None
    segs = sorted(ln.segs, key=lambda q: q.left)
    if len(segs) > 1 and segs[-1].text == "-" and not segs[-2].text.endswith(" "):
        segs[-1].text = SOFT
    for s in segs:
        if prev is not None:
            gap = s.left - prev.right
            if gap > max(2, s.size * 0.18) and not (parts and parts[-1][1].endswith(" ")) and not s.text.startswith(" ") and not getattr(s, "sup", False):
                parts.append((" ", " "))
        parts.append((seg_html(s), "" if getattr(s, "sup", False) else s.text))
        prev = s
    return parts


_SOFT_PAIRS = None


def soft_pairs():
    """Пары (конец строки, начало следующей) с автопереносом — по pdftotext, где он помечен U+2010."""
    global _SOFT_PAIRS
    if _SOFT_PAIRS is None:
        raw = subprocess.run(["pdftotext", "-raw", PDF, "-"], capture_output=True, text=True).stdout
        _SOFT_PAIRS = set(re.findall(r"(\w+)\u2010\s*\n\s*(\w+)", raw))
    return _SOFT_PAIRS


def glue(lines_parts):
    """Склейка строк абзаца: U+2010 в конце — авто-перенос (убираем), «-» и «_» в конце — без пробела."""
    h, p = "", ""
    for i, parts in enumerate(lines_parts):
        lh = "".join(a for a, _ in parts).rstrip()
        lp = "".join(b for _, b in parts).rstrip()
        if i == 0:
            h, p = lh.lstrip(), lp.lstrip()
            continue
        lh, lp = lh.lstrip(), lp.lstrip()
        if p.endswith(SOFT):
            h = h[: h.rfind(SOFT)] + h[h.rfind(SOFT) + 1:]
            p = p[:-1]
            h, p = h + lh, p + lp
        elif p.endswith("-") and not p.endswith(" -") and (re.search(r"(\w+)-$", p) or [None, ""]) and \
                (re.search(r"(\w+)-$", p).group(1), (re.match(r"(\w+)", lp) or [None, ""])[0] if re.match(r"(\w+)", lp) else "") in soft_pairs():
            h = h[: h.rfind("-")] + h[h.rfind("-") + 1:]
            h, p = h + lh, p[:-1] + lp
        elif p.endswith(("-", "_", "/")) and not p.endswith(" -"):
            h, p = h + lh, p + lp
        else:
            h, p = h + " " + lh, p + " " + lp
    h = re.sub(r"(</code>)(\s*)(<code>)", lambda m: m.group(2) if m.group(2) else "", h)
    return linkify(h), re.sub(r"\s+", " ", p).strip()


def linkify(h):
    h = re.sub(r'(?<![">])(https?://[^\s<]+[^\s<.,;)])', r'<a href="\1" rel="noopener">\1</a>', h)
    return re.sub(r"\s{2,}", " ", h)


# ------------------------------------------------------------------ фигуры
def crop_figure(pno, top, bottom, idx):
    name = f"fig_{idx:02d}.jpg"
    y0, y1 = int(top * SCALE), int(bottom * SCALE)
    x0, x1 = int(100 * SCALE), int(823 * SCALE)
    subprocess.run(["magick", page_png(pno), "-crop", f"{x1 - x0}x{y1 - y0}+{x0}+{y0}", "+repage", "-trim", "-bordercolor", "white",
                    "-border", "16", "-quality", "86", os.path.join(ADIR, name)], check=True)
    return name


# ------------------------------------------------------------------ значки в таблицах
def icon_at(pno, x0, x1, y0, y1):
    """Ищем значок (квадрат ~10 px) в прямоугольнике ячейки; возвращаем full / half / empty / None."""
    from_png = page_png(pno)
    X0, X1, Y0, Y1 = int(x0 * SCALE) + 3, int(x1 * SCALE) - 3, int(y0 * SCALE) + 3, int(y1 * SCALE) - 3
    if X1 <= X0 or Y1 <= Y0:
        return None
    raw = subprocess.run(["magick", from_png, "-crop", f"{X1 - X0}x{Y1 - Y0}+{X0}+{Y0}", "+repage", "-colorspace", "Gray",
                          "-depth", "8", "gray:-"], capture_output=True, check=True).stdout
    w, h = X1 - X0, Y1 - Y0
    dark = [(i % w, i // w) for i, v in enumerate(raw) if v < 110]
    if len(dark) < 12:
        return None
    xs, ys = [d[0] for d in dark], [d[1] for d in dark]
    bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    if bw > 60 or bh > 60 or bw < 8 or bh < 8:
        return None
    fill = len(dark) / (bw * bh)
    return "full" if fill > 0.8 else ("half" if fill > 0.5 else "empty")


ICON = {"full": '<i class="ic ic-f" title="есть штатно"></i>', "half": '<i class="ic ic-h" title="есть частично"></i>',
        "empty": '<i class="ic ic-e" title="нет"></i>'}
FW = ("ArduPilot", "PX4", "Betaflight", "INAV", "AP", "BF")


# ------------------------------------------------------------------ таблицы
def chunks(ln, gap=11):
    """Сегменты строки -> куски ячеек (разрыв больше gap px)."""
    out, cur = [], []
    for s in sorted(ln.segs, key=lambda q: q.left):
        if cur and s.left - max(c.right for c in cur) > gap and not getattr(s, "sup", False):
            out.append(cur)
            cur = []
        cur.append(s)
    if cur:
        out.append(cur)
    return out


def build_table(tlines, caption, pno_map):
    """tlines: строки таблицы (в т.ч. с разных страниц). Возвращает html."""
    # шапка — первая строка, если вся жирная
    header = None
    if tlines and all(s.bold or not s.text.strip() for s in tlines[0].segs) and len(chunks(tlines[0])) >= 2:
        header = tlines[0]
    body = [l for l in tlines if l is not header and not (header and l.text.strip() == header.text.strip())]
    # колонки по кускам тела
    starts = []
    for ln in body:
        for ch in chunks(ln):
            x = min(s.left for s in ch)
            if not any(abs(x - s0) <= 9 for s0 in starts):
                starts.append(x)
    starts.sort()
    # слить колонки, которые никогда не встречаются в одной строке и стоят близко
    merged = []
    for x in starts:
        if merged and x - merged[-1] < 40:
            continue
        merged.append(x)
    starts = merged
    hcells = []
    if header:
        for ch in chunks(header):
            x = min(s.left for s in ch)
            hcells.append((x, ch))
        hx = [x for x, _ in hcells]
        # шапка задаёт колонки, если в ней больше ячеек
        if len(hx) >= len(starts):
            starts = sorted(hx)
        elif hx and hx[0] > starts[0] + 40:
            pass
    ncol = max(1, len(starts))

    def col_of(x):
        best = 0
        for i, s0 in enumerate(starts):
            if x >= s0 - 30:
                best = i
        return best

    # строки таблицы
    rows, cur = [], None
    for ln in body:
        if cur is None or ln.page != cur["page"] or ln.top - cur["last_top"] > 23:
            cur = {"page": ln.page, "top": ln.top, "last_top": ln.top, "bottom": ln.bottom, "lines": []}
            rows.append(cur)
        cur["lines"].append(ln)
        cur["last_top"] = ln.top
        cur["bottom"] = max(cur["bottom"], ln.bottom)
    is_fw = header is not None and sum(any(f in header.text for f in FW[i:i + 1]) for i in range(len(FW))) >= 3
    plain_all = []
    hhtml = ""
    if header:
        cells = [""] * ncol
        cplain = [""] * ncol
        for x, ch in hcells:
            c = col_of(x)
            parts = [(seg_html(s), s.text) for s in ch]
            hh = "".join(a for a, _ in parts).strip()
            cells[c] = (cells[c] + " " + hh).strip()
            cplain[c] = (cplain[c] + " " + "".join(b for _, b in parts)).strip()
        plain_all.append(" ".join(cplain))
        hhtml = "<thead><tr>" + "".join(f'<th data-fw="{re.sub("<[^>]+>", "", c)}">{c}</th>' for c in cells) + "</tr></thead>"
    trs = []
    col_x = starts + [823]
    for r in rows:
        cells = [[] for _ in range(ncol)]
        for ln in r["lines"]:
            for ch in chunks(ln):
                c = col_of(min(s.left for s in ch))
                cells[c].append(ch)
        filled = [i for i in range(ncol) if cells[i]]
        italic_group = len(filled) == 1 and filled[0] == 0 and all(s.italic for ch in cells[0] for s in ch) and ncol > 2
        if italic_group:
            h_, p_ = glue([[(seg_html(s), s.text) for s in ch] for ch in cells[0]])
            trs.append(f'<tr class="grp"><td colspan="{ncol}">{h_}</td></tr>')
            plain_all.append(p_)
            continue
        tds, rowplain = [], []
        for i in range(ncol):
            if cells[i]:
                h_, p_ = glue([[(seg_html(s), s.text) for s in ch] for ch in cells[i]])
                tds.append(f"<td>{h_}</td>")
                rowplain.append(p_)
            elif is_fw and i > 0:
                ic = icon_at(r["page"], col_x[i] - (6 if i else 0), col_x[i + 1] - 6, r["top"] - 9, r["bottom"] + 9)
                tds.append(f'<td class="icn">{ICON.get(ic, "")}</td>')
            else:
                tds.append("<td></td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
        plain_all.append(" ".join(rowplain))
    cap = ""
    if caption:
        ch_, cp_ = glue([line_parts(l) for l in caption])
        cap = f"<caption>{ch_}</caption>"
        plain_all.insert(0, cp_)
    cls = "tbl fw" if is_fw else "tbl"
    return f'<div class="tblwrap reveal"><table class="{cls}">{cap}{hhtml}<tbody>{"".join(trs)}</tbody></table></div>', plain_all


# ------------------------------------------------------------------ основной проход
def convert(pages):
    blocks = []          # (kind, html, plain)
    toc = []
    fig_idx = 0
    foot = {}
    pending_table = None  # {"cap": [...], "lines": [...]}

    def flush_table():
        nonlocal pending_table
        if pending_table and pending_table["lines"]:
            h_, plain = build_table(pending_table["lines"], pending_table["cap"], None)
            blocks.append(("table", h_, " ".join(plain), pending_table["cap"] + pending_table["lines"]))
        elif pending_table and pending_table["cap"]:
            ch_, cp_ = glue([line_parts(l) for l in pending_table["cap"]])
            blocks.append(("p", f'<p class="cap">{ch_}</p>', cp_, pending_table["cap"]))
        pending_table = None

    para = None          # {"kind", "lines"}

    def flush_para():
        nonlocal para
        if para:
            h_, p_ = glue([line_parts(l) for l in para["lines"]])
            k = para["kind"]
            if k == "q":
                code = re.match(r"(Б\d+\.\d+)", p_).group(1)
                rest_h = re.sub(r"^\s*Б\s*\d+\.\d+\s*", "", re.sub(r"<[^>]+>", "", h_), count=1)
                blocks.append(("q", f'<h3 class="q" id="q-{code}"><span class="qc">{code}</span><span>{esc(rest_h)}</span></h3>', p_, para["lines"]))
            elif k == "li_num":
                m = re.match(r"\s*(\d+)\.\s*", re.sub(r"<[^>]+>", "", h_))
                blocks.append(("li_num", f"<li>{h_}</li>", p_, para["lines"]))
            elif k == "li_bul":
                blocks.append(("li_bul", f"<li>{h_}</li>", p_, para["lines"]))
            elif k == "body_s":
                blocks.append(("p", f'<p class="small">{h_}</p>', p_, para["lines"]))
            elif k == "note":
                blocks.append(("p", f'<p class="note">{h_}</p>', p_, para["lines"]))
            elif k == "h3":
                blocks.append(("h3", f"<h4>{h_}</h4>", p_, para["lines"]))
            else:
                blocks.append(("p", f"<p>{h_}</p>", p_, para["lines"]))
        para = None

    for pno, ph, pw, segs in pages:
        if pno in (1, 3):
            continue          # обложка и содержание собираются отдельно
        lines = attach_superscripts(X.lines_of(pno, segs))
        roles = [role(l) for l in lines]
        # фигуры: от подписи вверх до первой не-фигурной строки
        consumed = set()
        for i, (ln, r) in enumerate(zip(lines, roles)):
            if r != "fcap" or i in consumed:
                continue
            j = i - 1
            while j >= 0 and roles[j] in ("fig",):
                consumed.add(j)
                j -= 1
            top = (lines[j].bottom + 6) if j >= 0 else 80
            capl = [ln]
            k = i + 1
            while k < len(lines) and roles[k] in ("fcap", "cell", "fig") and lines[k].segs[0].color == "#333333" and lines[k].top - capl[-1].top < 24:
                capl.append(lines[k]); consumed.add(k); k += 1
            consumed.add(i)
            fig_idx += 1
            name = crop_figure(pno, top, ln.top - 4, fig_idx)
            ch_, cp_ = glue([line_parts(l) for l in capl])
            lines[i].fig = (name, ch_, cp_)
            lines[i].figlines = capl
        for i, (ln, r) in enumerate(zip(lines, roles)):
            if r in ("header", "pageno"):
                continue
            if hasattr(ln, "fig"):
                flush_para(); flush_table()
                name, ch_, cp_ = ln.fig
                blocks.append(("fig", f'<figure class="fig reveal"><div class="fimg"><img src="fig/{name}" alt="" loading="lazy"></div><figcaption>{ch_}</figcaption></figure>', cp_, ln.figlines))
                continue
            if i in consumed:
                continue
            if r == "foot":
                m = re.match(r"\s*(\d+)\.\s", ln.text)
                if m:
                    foot["cur"] = m.group(1)
                    foot.setdefault("items", []).append([m.group(1), [ln]])
                elif foot.get("items"):
                    foot["items"][-1][1].append(ln)
                continue
            if r == "h1":
                flush_para(); flush_table()
                h_, p_ = glue([line_parts(ln)])
                sid = f"s{len(toc) + 1}"
                toc.append((1, sid, p_))
                blocks.append(("h1", f'<h2 class="sec" id="{sid}">{h_}</h2>', p_, [ln]))
                continue
            if r == "h2":
                flush_para(); flush_table()
                h_, p_ = glue([line_parts(ln)])
                sid = f"s{len(toc) + 1}"
                toc.append((2, sid, p_))
                blocks.append(("h2", f'<h3 class="sub" id="{sid}">{h_}</h3>', p_, [ln]))
                continue
            if r == "q":
                flush_para(); flush_table()
                para = {"kind": "q", "lines": [ln]}
                continue
            if r == "qcont_or_h3":
                if para and para["kind"] == "q" and ln.top - para["lines"][-1].top < 26:
                    para["lines"].append(ln)
                else:
                    flush_para(); flush_table()
                    para = {"kind": "h3", "lines": [ln]}
                    flush_para()
                continue
            if r == "tcap":
                flush_para(); flush_table()
                pending_table = {"cap": [ln], "lines": []}
                continue
            if r == "cell":
                flush_para()
                if pending_table is None:
                    pending_table = {"cap": [], "lines": []}
                pending_table["lines"].append(ln)
                continue
            if r in ("body", "body_s", "note"):
                flush_table()
                kind = {"body": "p", "body_s": "body_s", "note": "note"}[r]
                txt = ln.text.strip()
                if r == "body" and 112 <= ln.left <= 124 and re.match(r"\d+\.\s", txt):
                    flush_para(); para = {"kind": "li_num", "lines": [ln]}; continue
                if r == "body" and 108 <= ln.left <= 114 and re.match(r"1\d\.\s", txt):
                    flush_para(); para = {"kind": "li_num", "lines": [ln]}; continue
                if para and para["kind"] in ("li_num", "li_bul") and 125 <= ln.left <= 145:
                    prev = para["lines"][-1]
                    if para["kind"] == "li_bul" and ln.top - prev.top > 30:
                        flush_para(); para = {"kind": "li_bul", "lines": [ln]}
                    else:
                        para["lines"].append(ln)
                    continue
                if r == "body" and 125 <= ln.left <= 145:
                    flush_para(); para = {"kind": "li_bul", "lines": [ln]}; continue
                new = (para is None or para["kind"] != kind or ln.left >= 150
                       or (ln.page == para["lines"][-1].page and ln.top - para["lines"][-1].top > 34))
                if new:
                    flush_para()
                    para = {"kind": kind, "lines": [ln]}
                else:
                    para["lines"].append(ln)
                continue
            if r == "fig":
                continue
        # конец страницы: абзац может продолжиться на следующей, таблица тоже
        if foot.get("items"):
            flush_para(); flush_table()
            for n, fl in foot["items"]:
                h_, p_ = glue([line_parts(l) for l in fl])
                h_ = re.sub(r"^\s*" + n + r"\.\s*", "", h_)
                blocks.append(("foot", f'<aside class="fn" id="fn-{n}"><a href="#fnref-{n}">{n}.</a> {h_}</aside>', p_, fl))
            foot = {}
    flush_para(); flush_table()
    return blocks, toc


def cover(pages):
    segs = pages[0][3]
    lines = X.lines_of(1, segs)
    t = [l.text.strip() for l in lines]
    return lines, t


# ------------------------------------------------------------------ сверка
def words(s):
    s = s.replace(SOFT, "")
    return re.findall(r"[\w\-–—«»\"'%°/.,:;()+=*№×≥≤±→]+", s)


def verify(blocks, pages):
    """1) каждая не-фигурная строка PDF ровно в одном блоке; 2) слова блока = слова его строк
    (текст — по порядку, таблицы — как набор); 3) число снятых переносов = числу U+2010 в pdftotext."""
    from collections import Counter
    used = Counter(id(l) for b in blocks for l in b[3])
    problems = []
    total = 0
    for pno, ph, pw, segs in pages:
        if pno in (1, 3):
            continue
    for b in blocks:
        kind, h_, plain, src = b
        if kind == "table":
            # посимвольно: буквы и цифры источника = буквы и цифры результата (дефисы переносов и пробелы не считаем)
            sw = Counter(c for c in "".join(s_.text for l in src for s_ in l.segs if not getattr(s_, "sup", False)) if c.isalnum() or c in "%°±≥≤«»()")
            ow = Counter(c for c in plain if c.isalnum() or c in "%°±≥≤«»()")
            if sw != ow:
                problems.append((kind, "символы", "".join(sorted((sw - ow).elements()))[:40], "".join(sorted((ow - sw).elements()))[:40]))
        else:
            _, sp = glue([line_parts(l) for l in src])
            if words(sp) != words(plain):
                problems.append((kind, "порядок", sp[:90], plain[:90]))
        total += len(words(plain))
    dup = [k for k, v in used.items() if v > 1]
    soft_out = sum(1 for b in blocks for l in b[3] if l.segs and l.segs[-1].text == SOFT)
    soft_out += sum(len(re.findall(r"\w-\w", "")) for b in blocks)
    raw = subprocess.run(["pdftotext", "-raw", PDF, "-"], capture_output=True, text=True).stdout
    soft_pdf = raw.count(SOFT)
    return total, problems, dup, soft_out, soft_pdf


def coverage(pages, blocks):
    ids = set(id(l) for b in blocks for l in b[3])
    miss = []
    return miss



# ------------------------------------------------------------------ вёрстка страницы
DOC_CSS = r"""
:root { --bg:#0D0E10; --fg:#E9E9E6; --fg-2:#A4A9B0; --muted:#6F757D; --rule:#24272C; --panel:#131518; --zebra:#111316;
  --accent:#FF5A1F; --accent-text:#FF7A45; --code:#F2C3A8; --figbg:#F4F4F2;
  --word:"Michroma","Arial",sans-serif; --display:"Unbounded","Arial",sans-serif; --body:"IBM Plex Sans",system-ui,sans-serif;
  --serif:"IBM Plex Serif","PT Serif",Georgia,serif; --mono:"IBM Plex Mono",Menlo,monospace; --ease:cubic-bezier(.2,.7,.1,1); color-scheme:dark; }
:root[data-theme="light"] { --bg:#E9E9E6; --fg:#0D0E10; --fg-2:#464B53; --muted:#767B83; --rule:#CDD0D4; --panel:#F2F2EF; --zebra:#E2E3E0;
  --accent-text:#C73E0C; --code:#8A2E0A; --figbg:#FFFFFF; color-scheme:light; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { --bg:#E9E9E6; --fg:#0D0E10; --fg-2:#464B53; --muted:#767B83; --rule:#CDD0D4;
  --panel:#F2F2EF; --zebra:#E2E3E0; --accent-text:#C73E0C; --code:#8A2E0A; --figbg:#FFFFFF; color-scheme:light; } }
* { box-sizing:border-box; } [hidden] { display:none !important; }
body { margin:0; background:var(--bg); color:var(--fg); font:17px/1.68 var(--serif); -webkit-font-smoothing:antialiased; }
a { color:var(--accent-text); text-decoration-thickness:1px; text-underline-offset:3px; }
.bar { position:sticky; top:env(safe-area-inset-top,0px); z-index:20; background:color-mix(in srgb,var(--bg) 82%,transparent); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); border-bottom:1px solid var(--rule); }
body::before { content:""; position:fixed; inset:0 0 auto; height:env(safe-area-inset-top,0px); z-index:30; background:var(--bg); }
.bar .in { display:flex; align-items:center; gap:18px; min-height:60px; padding-left:max(20px,env(safe-area-inset-left,0px)); padding-right:max(20px,env(safe-area-inset-right,0px)); }
.bar .word { font:400 13px var(--word); letter-spacing:.14em; text-decoration:none; color:var(--fg); }
.bar code { font:500 12px var(--mono); color:var(--muted); }
.bar .sp { margin-left:auto; display:flex; gap:8px; align-items:center; }
.bar a.b, .bar button { font:500 13px var(--body); color:var(--fg); text-decoration:none; padding:7px 13px; border:1px solid var(--rule); border-radius:99px; background:none; cursor:pointer; transition:background .3s,color .3s; }
.bar a.b:hover, .bar button:hover { background:var(--fg); color:var(--bg); }
.prog { position:absolute; left:0; bottom:-1px; height:2px; background:var(--accent); width:0; transition:width .15s linear; }
.cover { position:relative; overflow:hidden; border-bottom:1px solid var(--rule); }
.cover .in { max-width:1180px; margin:0 auto; padding:80px max(20px,env(safe-area-inset-right,0px)) 70px max(20px,env(safe-area-inset-left,0px)); display:grid; gap:22px; }
.cover .org { font:400 13px var(--word); letter-spacing:.2em; color:var(--fg-2); }
.cover .kind { font:500 13px var(--body); letter-spacing:.42em; text-transform:uppercase; color:var(--accent-text); }
.cover h1 { font:500 clamp(24px,4.2vw,52px)/1.08 var(--display); hyphens:auto; overflow-wrap:break-word; margin:0; max-width:15em; text-wrap:balance; }
.cover h1 span { display:block; overflow:hidden; } .cover h1 em { display:block; font-style:normal; animation:rise 1.1s var(--ease) both; }
.cover h1 span:nth-child(2) em { animation-delay:.1s; } .cover h1 span:nth-child(3) em { animation-delay:.2s; }
@keyframes rise { from { transform:translateY(105%); } }
.cover .sub { font:400 clamp(17px,1.6vw,21px)/1.5 var(--serif); color:var(--fg-2); max-width:36em; }
.cover .meta { display:flex; flex-wrap:wrap; gap:10px 40px; margin-top:20px; padding-top:20px; border-top:1px solid var(--rule); font:15px var(--body); }
.cover .meta span { color:var(--muted); display:block; font:500 11px var(--mono); letter-spacing:.1em; text-transform:uppercase; margin-bottom:4px; }
.cover .fnc { font:13px var(--body); color:var(--muted); }
.cover .city { font:400 12px var(--word); letter-spacing:.2em; color:var(--muted); }
.cover svg.rings { position:absolute; right:-6%; top:50%; width:min(560px,52vw); transform:translateY(-50%); opacity:.9; pointer-events:none; }
.layout { max-width:1180px; margin:0 auto; display:grid; grid-template-columns:250px minmax(0,1fr); gap:56px; padding:40px max(20px,env(safe-area-inset-right,0px)) 80px max(20px,env(safe-area-inset-left,0px)); }
nav.toc { position:sticky; top:84px; align-self:start; max-height:calc(100vh - 110px); overflow:auto; font:13px/1.4 var(--body); padding-right:6px; }
nav.toc .h { font:500 11px var(--mono); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-bottom:10px; }
nav.toc a { display:block; color:var(--fg-2); text-decoration:none; padding:5px 0 5px 12px; border-left:2px solid var(--rule); transition:color .3s,border-color .3s,padding .3s var(--ease); }
nav.toc a.l2 { padding-left:24px; font-size:12px; }
nav.toc a.on { color:var(--fg); border-left-color:var(--accent); padding-left:16px; }
nav.toc a.l2.on { padding-left:28px; }
article { min-width:0; max-width:780px; }
article h2.sec { font:500 clamp(20px,2.8vw,34px)/1.15 var(--display); hyphens:auto; overflow-wrap:break-word; margin:72px 0 22px; padding-top:18px; border-top:1px solid var(--rule); scroll-margin-top:80px; }
article h2.sec:first-child { margin-top:0; }
article h3.sub { font:500 21px/1.3 var(--display); margin:40px 0 14px; scroll-margin-top:80px; }
article h4 { font:600 16px var(--body); margin:28px 0 10px; }
article h3.q { display:grid; grid-template-columns:62px minmax(0,1fr); gap:12px; font:600 17px/1.4 var(--body); margin:36px 0 10px; scroll-margin-top:84px; }
article h3.q .qc { font:500 12px var(--mono); color:var(--accent-text); padding-top:3px; }
article p { margin:0 0 14px; text-wrap:pretty; }
article p.small { font-size:15px; color:var(--fg-2); }
article p.note { font:14px/1.5 var(--body); color:var(--muted); }
article p.cap { font:600 14px var(--body); margin-top:26px; }
article code { font:500 .86em var(--mono); color:var(--code); background:color-mix(in srgb,var(--accent) 9%,transparent); padding:1px 5px; border-radius:3px; }
article ol, article ul { margin:0 0 16px; padding-left:26px; }
article li { margin-bottom:8px; }
.tblwrap { overflow-x:auto; margin:22px 0 22px; }
table.tbl { width:100%; border-collapse:collapse; font:14px/1.45 var(--body); }
table.tbl caption { text-align:left; font:600 14px var(--body); padding-bottom:10px; color:var(--fg); }
table.tbl th { text-align:left; font:600 13px var(--body); padding:10px 12px; border-bottom:1.5px solid var(--fg); white-space:nowrap; }
table.tbl td { padding:9px 12px; border-bottom:1px solid var(--rule); vertical-align:top; }
table.tbl tbody tr:nth-child(even) td { background:var(--zebra); }
table.tbl td:first-child { font-weight:600; }
table.tbl tr.grp td { font:italic 600 13px var(--body); color:var(--accent-text); background:none; padding-top:16px; }
table.tbl td.icn { text-align:center; vertical-align:middle; }
th[data-fw="ArduPilot"]::before, th[data-fw="AP"]::before { content:"■ "; } th[data-fw="PX4"]::before { content:"▲ "; }
th[data-fw="Betaflight"]::before, th[data-fw="BF"]::before { content:"● "; } th[data-fw="INAV"]::before { content:"◆ "; }
th[data-fw]::before { color:var(--accent); font-size:.8em; }
.ic { display:inline-block; width:12px; height:12px; border:1.5px solid var(--fg); vertical-align:-1px; }
.ic-f { background:var(--fg); } .ic-h { background:linear-gradient(90deg,var(--fg) 50%,transparent 50%); } .ic-e { background:none; opacity:.7; }
.tblwrap.anim tbody tr { animation:row .6s var(--ease) both; }
@keyframes row { from { opacity:0; transform:translateY(6px); } }
figure.fig { margin:28px 0; }
figure.fig .fimg { background:var(--figbg); padding:10px; border:1px solid var(--rule); cursor:zoom-in; overflow:hidden; }
figure.fig img { width:100%; height:auto; display:block; transition:transform .8s var(--ease); }
figure.fig .fimg:hover img { transform:scale(1.015); }
figure.fig figcaption { font:13px/1.45 var(--body); color:var(--fg-2); margin-top:10px; text-align:center; }
aside.fn { font:13px/1.5 var(--body); color:var(--muted); border-left:2px solid var(--accent); padding:4px 0 4px 12px; margin:10px 0 18px; }
sup.fnref a { font:600 11px var(--mono); text-decoration:none; }
.end { text-align:center; font:400 12px var(--word); letter-spacing:.3em; color:var(--muted); margin-top:60px; }
.reveal { transition:opacity .8s var(--ease), transform .8s var(--ease); } .pre { opacity:0; transform:translateY(18px); }
.lb { position:fixed; inset:0; z-index:50; background:rgba(6,7,8,.92); display:grid; place-items:center; padding:max(20px,env(safe-area-inset-top,0px)) 20px; cursor:zoom-out; animation:fade .3s both; }
.lb img { max-width:100%; max-height:100%; background:#fff; }
@keyframes fade { from { opacity:0; } }
::view-transition-old(root) { animation:fade .35s reverse both; } ::view-transition-new(root) { animation:fade .45s both; }
@media (max-width:900px) { .layout { grid-template-columns:minmax(0,1fr); gap:0; } nav.toc { display:none; } .cover svg.rings { opacity:.25; } }
@media (max-width:560px) { article h3.q { grid-template-columns:minmax(0,1fr); gap:2px; } .bar code { display:none; } body { font-size:16px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; } .pre { opacity:1; transform:none; } }
"""

DOC_JS = r"""
(function(){
  const root=document.documentElement, reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  try{const t=localStorage.getItem('ubv-theme'); if(t) root.dataset.theme=t;}catch(e){}
  const light=()=>root.dataset.theme?root.dataset.theme==='light':matchMedia('(prefers-color-scheme: light)').matches;
  document.getElementById('theme').addEventListener('click',()=>{const go=()=>{root.dataset.theme=light()?'dark':'light';try{localStorage.setItem('ubv-theme',root.dataset.theme);}catch(e){}};document.startViewTransition&&!reduce?document.startViewTransition(go):go();});
  const prog=document.querySelector('.prog');
  const heads=[...document.querySelectorAll('article h2.sec, article h3.sub')], links=new Map([...document.querySelectorAll('nav.toc a')].map(a=>[a.getAttribute('href').slice(1),a]));
  function onScroll(){
    const h=document.documentElement; prog.style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+'%';
    let cur=null; for(const el of heads){ if(el.getBoundingClientRect().top<120) cur=el; else break; }
    links.forEach(a=>a.classList.remove('on')); if(cur&&links.get(cur.id)){const a=links.get(cur.id); a.classList.add('on'); if(a.offsetParent){const n=a.closest('nav'); if(a.offsetTop<n.scrollTop||a.offsetTop>n.scrollTop+n.clientHeight-40) n.scrollTo({top:a.offsetTop-80,behavior:'smooth'});}}
  }
  addEventListener('scroll',onScroll,{passive:true}); onScroll();
  if(!reduce&&'IntersectionObserver' in window){
    const io=new IntersectionObserver(es=>es.forEach(en=>{if(en.isIntersecting){en.target.classList.remove('pre'); if(en.target.classList.contains('tblwrap')){en.target.classList.add('anim'); en.target.querySelectorAll('tbody tr').forEach((tr,i)=>tr.style.animationDelay=Math.min(i*35,600)+'ms');} io.unobserve(en.target);}}),{rootMargin:'0px 0px -6% 0px'});
    document.querySelectorAll('.reveal').forEach(el=>{ if(el.getBoundingClientRect().top>innerHeight*.95){el.classList.add('pre'); io.observe(el);} });
  }
  document.addEventListener('click',e=>{const f=e.target.closest('.fimg'); if(!f) return; const lb=document.createElement('div'); lb.className='lb'; lb.innerHTML='<img alt="">'; lb.firstChild.src=f.querySelector('img').src; lb.addEventListener('click',()=>lb.remove()); document.body.appendChild(lb);});
  addEventListener('keydown',e=>{if(e.key==='Escape') document.querySelector('.lb')?.remove();});
  const svg=document.querySelector('svg.rings'); if(svg&&window.UBVRings) UBVRings(svg);
})();
"""


def cover_html(pages):
    lines = X.lines_of(1, pages[0][3])
    groups = []
    for ln in lines:
        k = ln.main()
        if groups and groups[-1][0] == k and ln.top - groups[-1][1][-1].top < 50:
            groups[-1][1].append(ln)
        else:
            groups.append((k, [ln]))
    g = {}
    for k, ls in groups:
        h_, p_ = glue([line_parts(l) for l in ls])
        g.setdefault((k[0], k[1][:6], k[3]), []).append((h_, p_, [l.text for l in ls]))
    title_lines = [l.text.strip() for l in lines if l.main()[0] == 33]
    sub = g[(18, "PTSeri", False)][0][0]
    kind = re.sub(r"\s(?=\S)", "", next(l.text for l in lines if "Н А Л" in l.text)).replace("Я", "Я ", 1).strip()
    kind = "АНАЛИТИЧЕСКАЯ СПРАВКА"
    org = next(l.text for l in lines if l.text.strip() == "UBVPROJECT")
    city1 = next(l.text for l in lines if l.text.strip() == "Санкт-Петербург")
    prep = next(l.text for l in lines if l.text.startswith("Подготовлено"))
    author = next(l.text for l in lines if l.text.startswith("Всеволод"))
    rev = next(l.text for l in lines if l.text.startswith("Редакция"))
    fn = next(l.text for l in lines if l.text.startswith("*"))
    city2 = next(l.text for l in lines if l.text.startswith("Санкт-Петербург 2026"))
    plain = " ".join([org, city1, kind, " ".join(title_lines), re.sub("<[^>]+>", "", sub), prep, author, rev, fn, city2])
    h = (f'<header class="cover"><svg class="rings sym" viewBox="0 0 200 200" aria-hidden="true"></svg><div class="in">'
         f'<div class="org">{esc(org)} · <span class="city">{esc(city1)}</span></div><div class="kind">{esc(kind)}</div>'
         f'<h1>{"".join(f"<span><em>{esc(t)}</em></span>" for t in title_lines)}</h1><p class="sub">{sub}</p>'
         f'<div class="meta"><div><span>Обозначение</span>{esc(META.get("code", ""))}</div><div><span>{esc(prep)}</span>{esc(author)}</div><div><span>Редакция</span>{esc(rev)}</div></div>'
         f'<p class="fnc">{esc(fn)}</p><p class="city">{esc(city2)}</p></div></header>')
    return h, plain


RINGS_JS = r"""
window.UBVRings=function(svg){
  const NS='http://www.w3.org/2000/svg', C=100, R=78, N=120, reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const css=getComputedStyle(document.documentElement);
  const rings=[[1,0,0],[0,1,0],[0,0,1]].map((n,k)=>{const f=document.createElementNS(NS,'path'),b=document.createElementNS(NS,'path');
    [b,f].forEach(p=>{p.setAttribute('fill','none'); p.style.stroke=k===1?'var(--accent)':'var(--rule)'; svg.appendChild(p);});
    b.setAttribute('stroke-width','.6'); b.setAttribute('stroke-dasharray','2 4'); f.setAttribute('stroke-width',k===1?'2.2':'1.4');
    const a=Math.abs(n[0])<.9?[1,0,0]:[0,1,0]; let e1=[a[1]*n[2]-a[2]*n[1],a[2]*n[0]-a[0]*n[2],a[0]*n[1]-a[1]*n[0]]; const L=Math.hypot(...e1); e1=e1.map(v=>v/L);
    const e2=[n[1]*e1[2]-n[2]*e1[1],n[2]*e1[0]-n[0]*e1[2],n[0]*e1[1]-n[1]*e1[0]]; return {f,b,e1,e2};});
  let yaw=20,last=performance.now();
  function draw(){const cy=Math.cos(yaw*Math.PI/180),sy=Math.sin(yaw*Math.PI/180),t=22*Math.PI/180,ct=Math.cos(t),st=Math.sin(t);
    rings.forEach(r=>{let f='',bk='',pf=0,pb=0;for(let i=0;i<=N;i++){const u=2*Math.PI*i/N;let x=Math.cos(u)*r.e1[0]+Math.sin(u)*r.e2[0],y=Math.cos(u)*r.e1[1]+Math.sin(u)*r.e2[1],z=Math.cos(u)*r.e1[2]+Math.sin(u)*r.e2[2];
      [x,z]=[x*cy+z*sy,-x*sy+z*cy];[y,z]=[y*ct-z*st,y*st+z*ct];const X=(C+x*R).toFixed(1),Y=(C-y*R).toFixed(1);
      if(z>=0){f+=(pf?'L':'M')+X+' '+Y;pf=1;pb=0;}else{bk+=(pb?'L':'M')+X+' '+Y;pb=1;pf=0;}}r.f.setAttribute('d',f);r.b.setAttribute('d',bk);});}
  function tick(now){yaw+=6*Math.min(64,now-last)/1000;last=now;draw();requestAnimationFrame(tick);}
  draw(); if(!reduce) requestAnimationFrame(tick);
};
"""


def legend(h):
    """«В таблицах: есть штатно, есть частично, нет.» — вставляем значки перед словами (текст не меняется)."""
    return (h.replace("В таблицах: есть штатно,", f'В таблицах: {ICON["full"]} есть штатно,')
             .replace(" есть частично,", f' {ICON["half"]} есть частично,', 1)
             .replace(" частично, нет.", f' частично, {ICON["empty"]} нет.', 1))


def render(blocks, toc, pages):
    cov, cov_plain = cover_html(pages)
    body = []
    open_list = None
    for kind, h_, plain, *_ in blocks:
        if kind in ("li_num", "li_bul"):
            tag = "ol" if kind == "li_num" else "ul"
            if open_list != tag:
                if open_list:
                    body.append(f"</{open_list}>")
                body.append(f'<{tag} class="reveal">')
                open_list = tag
            if kind == "li_num":
                h_ = re.sub(r"^\s*(?:<b>)?\s*\d+\.\s*", lambda m: "<b>" if "<b>" in m.group(0) else "", h_, count=1)
            body.append(h_)
            continue
        if open_list:
            body.append(f"</{open_list}>")
            open_list = None
        if "В таблицах:" in h_:
            h_ = legend(h_)
        if "К О Н Е Ц" in plain:
            body.append(f'<p class="end">{h_}</p>')
            continue
        body.append(h_)
    if open_list:
        body.append(f"</{open_list}>")
    tochtml = "".join(f'<a href="#{sid}" class="l{lvl}">{esc(t)}</a>' for lvl, sid, t in toc)
    html_ = (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
             f'<title>{esc(META.get("title", ""))}</title>'
             f'<meta name="description" content="{html.escape(META.get("description", ""), quote=True)}">'
             f'<link rel="canonical" href="{META.get("url", "")}"><meta property="og:type" content="article">'
             f'<meta property="og:site_name" content="UBVPROJECT"><meta property="og:locale" content="ru_RU">'
             f'<meta property="og:title" content="{html.escape(META.get("title", ""), quote=True)}">'
             f'<meta property="og:description" content="{html.escape(META.get("description", ""), quote=True)}">'
             f'<meta property="og:url" content="{META.get("url", "")}"><meta property="og:image" content="{META.get("og_image", "")}">'
             f'<meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#0D0E10">'
             f'<link rel="icon" href="../../assets/logo.svg" type="image/svg+xml">'
             f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,600;1,600&family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&family=Michroma&family=Unbounded:wght@500&display=swap">'
             f'<style>{DOC_CSS}</style></head><body>'
             f'<div class="bar"><div class="in"><a class="word" href="../../">UBVPROJECT</a><code>{esc(META.get("code_line", ""))}</code>'
             f'<span class="sp"><button id="theme" type="button" aria-label="Сменить тему">Тема</button><a class="b" href="{META.get("pdf", "")}">PDF</a><a class="b" href="../../#docs">← Сайт</a></span></div><i class="prog"></i></div>'
             f'{cov}<div class="layout"><nav class="toc" aria-label="Содержание"><div class="h">Содержание</div>{tochtml}</nav>'
             f'<article>{"".join(body)}</article></div><script>{RINGS_JS}{DOC_JS}</script></body></html>')
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_)
    return len(html_), cov_plain


def run(pdf, out_dir, tmp_dir, meta):
    """Полный цикл: разбор, сверка, вёрстка. Возвращает отчёт сверки; при расхождениях — исключение."""
    configure(pdf, out_dir, tmp_dir, meta)
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(ADIR, exist_ok=True)
    for f in os.listdir(ADIR):
        os.remove(os.path.join(ADIR, f))
    pages = prepare()
    blocks, toc = convert(pages)
    total, problems, dup, soft_out, soft_pdf = verify(blocks, pages)
    if problems or dup:
        raise RuntimeError(f"сверка не прошла: {len(problems)} расхождений, {len(dup)} задвоений — текст не публикую")
    n, _ = render(blocks, toc, pages)
    return {"words": total, "tables": sum(1 for b in blocks if b[0] == "table"), "figures": sum(1 for b in blocks if b[0] == "fig"),
            "questions": sum(1 for b in blocks if b[0] == "q"), "size_kb": n // 1024}
