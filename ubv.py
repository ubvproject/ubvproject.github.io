#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сайт UBVPROJECT: редактор, документы и сборка страниц.

    python3 ubv.py cms                       редактор сайта в браузере: http://localhost:8091/admin/  (правки только локально)
    python3 ubv.py build [--images]          пересобрать все страницы из _content/*.json (--images — заново картинки превью)
    python3 ubv.py preview                   открыть сайт локально: http://localhost:8090
    python3 ubv.py add путь/к/файлу.pdf      добавить документ (или новую редакцию) — спросит код, название, аннотацию
    python3 ubv.py web UBV-AS-2026-01        сделать веб-версию справки из её PDF (текст не меняется, сверка слово в слово)
    python3 ubv.py link UBV-AS-2026-01 URL   привязать пост в канале к документу
    python3 ubv.py publish ["сообщение"]     собрать, закоммитить и отправить на GitHub

Содержимое — _content/*.json (site, home, optimum, tech, news, projects, about, docs), тема — _tools/theme.py,
assets/site.css, assets/site.js, пиктограммы — _tools/icons/. Нужны: Google Chrome (картинки превью),
poppler (pdfinfo, pdftoppm, pdftohtml) и ImageMagick (веб-версия справки): brew install poppler imagemagick.
"""
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "_content")
TPL = os.path.join(ROOT, "_tools", "templates")
SITE_JSON = os.path.join(CONTENT, "site.json")
DOCS_JSON = os.path.join(CONTENT, "docs.json")
PROJECTS_JSON = os.path.join(CONTENT, "projects.json")
SECTIONS = ("site", "home", "optimum", "tech", "news", "projects", "about", "docs")
sys.path.insert(0, os.path.join(ROOT, "_tools"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()


# ---------- данные ----------

def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def slug(code):
    return code.lower()


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def ru_date(iso):
    return datetime.date.fromisoformat(iso).strftime("%d.%m.%Y")


def esc(s):
    return html.escape(s or "", quote=True)


# ---------- шаблоны ----------

def tpl(name):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        return f.read()


def fill(text, **ctx):
    """{{ключ}} → значение; один проход, подставленное повторно не разбирается"""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx[m.group(1)]), text)


def logo():
    with open(os.path.join(ROOT, "assets", "logo.svg"), encoding="utf-8") as f:
        return f.read().strip().replace("<svg ", '<svg aria-hidden="true" ', 1)


def content():
    """Всё содержимое сайта: {раздел: данные из _content/<раздел>.json}"""
    return {k: load(os.path.join(CONTENT, k + ".json"), [] if k == "docs" else {}) for k in SECTIONS}



def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)





# ---------- сборка ----------

def build(images=False):
    import theme
    c = content()
    site, docs = c["site"], sorted(c["docs"], key=lambda d: d["code"], reverse=True)
    write("index.html", theme.home_page(c))
    write("docs/index.html", theme.docs_redirect(c))
    write("404.html", theme.not_found(c))
    for d in docs:
        dirp = os.path.join(ROOT, "docs", slug(d["code"]))
        if d.get("web") and os.path.exists(os.path.join(dirp, "index.html")) and "fig/" in open(os.path.join(dirp, "index.html"), encoding="utf-8").read(200000):
            continue                     # веб-версия справки — её делает «ubv.py web», сборка её не трогает
        write("docs/%s/index.html" % slug(d["code"]), theme.doc_landing(c, d))

    og_home = os.path.join(ROOT, "assets", "og", "home.png")
    if images or not os.path.exists(og_home):
        render_og(og_home, kind=c["home"]["kicker"], title=" ".join(c["home"]["title"]),
                  meta='<span>%s</span>' % esc(site["telegram"]["name"]))
    for d in docs:
        dirp = os.path.join(ROOT, "docs", slug(d["code"]))
        if images or not os.path.exists(os.path.join(dirp, "og.png")):
            doc_images(d)

    own = [p for p in c["projects"].get("own", []) if p.get("path") and p.get("page")]
    for p in own:
        write(p["path"] + "index.html", theme.project_page(c, p))
    partners = [p["path"] for p in c["projects"].get("partners", []) if p.get("path")]
    urls = [""] + [p["path"] for p in own] + ["docs/%s/" % slug(d["code"]) for d in docs] + partners
    base = site["base_url"].rstrip("/") + "/"
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join("  <url><loc>%s%s</loc></url>\n" % (base, u) for u in urls) + "</urlset>\n")
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % base)
    print("собрано: главная (%d вкладок), %d %s" % (len(site["nav"]), len(docs), plural(len(docs), "документ", "документа", "документов")))


def cmd_web(code):
    """Веб-версия справки из PDF: текст переносится без изменений и сверяется слово в слово."""
    from docweb import doc_web
    for t in ("pdftohtml", "pdftoppm", "pdftotext", "magick"):
        need(t, "brew install poppler imagemagick")
    docs = load(DOCS_JSON, [])
    d = next((x for x in docs if x["code"] == code.upper()), None)
    if not d:
        sys.exit("нет документа %s" % code)
    s = slug(d["code"])
    dirp = os.path.join(ROOT, "docs", s)
    base = load(SITE_JSON, {})["base_url"].rstrip("/") + "/"
    meta = {"title": "%s · %s — UBVPROJECT" % (d["code"], d["short"]), "description": d["summary"], "url": base + "docs/%s/" % s,
            "og_image": base + "docs/%s/og.png" % s, "pdf": d["pdf"], "code": d["code"],
            "code_line": "%s · ред. %s" % (d["code"], d["edition"])}
    rep = doc_web.run(os.path.join(dirp, d["pdf"]), dirp, os.path.join(ROOT, "_tools", ".cache", s), meta)
    d["web"] = True
    save(DOCS_JSON, docs)
    print("веб-версия %s: %d слов, %d вопросов, %d таблиц, %d рисунков — сверка с PDF без расхождений"
          % (d["code"], rep["words"], rep["questions"], rep["tables"], rep["figures"]))
    build()


# ---------- картинки: обложка и превью для Telegram ----------

def need(tool, hint):
    if not shutil.which(tool):
        sys.exit("нет %s — %s" % (tool, hint))


def doc_images(d):
    dirp = os.path.join(ROOT, "docs", slug(d["code"]))
    need("pdftoppm", "brew install poppler")
    subprocess.run(["pdftoppm", "-png", "-r", "100", "-f", "1", "-l", "1", "-singlefile",
                    os.path.join(dirp, d["pdf"]), os.path.join(dirp, "cover")], check=True)
    meta = '<span class="code">%s</span>' % esc(d["code"])
    if d.get("client"):
        meta += "<span>для %s</span>" % esc(d["client"])
    render_og(os.path.join(dirp, "og.png"), kind=d["kind"], title=d["short"], meta=meta,
              cover=os.path.join(dirp, "cover.png"))


def render_og(out, *, kind, title, meta, cover=None):
    """Карточка 1200×630 для превью ссылки: скриншот HTML через headless Chrome"""
    if not os.path.exists(CHROME):
        print("  ! нет Google Chrome — картинка превью %s не создана" % os.path.relpath(out, ROOT))
        return
    right = '<div class="r"><img src="file://%s"></div>' % cover if cover else ""
    size = 58 if len(title) <= 40 else 48 if len(title) <= 70 else 40
    tmp = os.path.join(ROOT, "_tools", ".og.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(fill(tpl("og.html"), logo=logo(), kind=esc(kind), title=esc(title), meta=meta, right=right, title_size=size))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--allow-file-access-from-files", "--virtual-time-budget=4000", "--window-size=1200,630", "--screenshot=" + out, "file://" + tmp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        os.remove(tmp)


# ---------- команды ----------

def ask(q, default=""):
    a = input("%s%s: " % (q, " [%s]" % default if default else "")).strip()
    return a or default


def pdf_info(path):
    info = {}
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
        for k in ("Title", "Pages"):
            m = re.search(r"^%s:\s+(.*)$" % k, out, flags=re.M)
            if m:
                info[k] = m.group(1).strip()
    mb = os.path.getsize(path) / 1e6
    info["size"] = ("%.1f МБ" % mb).replace(".", ",") if mb >= 1 else "%d КБ" % (os.path.getsize(path) // 1000)
    return info


def cmd_add(pdf):
    pdf = os.path.expanduser(pdf)
    if not os.path.isfile(pdf) or not pdf.lower().endswith(".pdf"):
        sys.exit("нужен путь к PDF")
    docs = load(DOCS_JSON, [])
    info = pdf_info(pdf)
    year = datetime.date.today().year
    nums = [int(m.group(1)) for d in docs for m in [re.match(r"UBV-AS-%d-(\d+)$" % year, d["code"])] if m]
    print("Добавляю %s (%s стр., %s). Enter — значение в скобках.\n" % (os.path.basename(pdf), info.get("Pages", "?"), info["size"]))

    code = ask("Код документа", "UBV-AS-%d-%02d" % (year, max(nums, default=0) + 1)).upper()
    old = next((d for d in docs if d["code"] == code), {})
    if old:
        print("  %s уже есть — обновлю его. Старые значения в скобках." % code)
    title = ask("Полное название", old.get("title") or re.sub(r"\s+—\s+UbVProject$", "", info.get("Title", "")))
    d = dict(old)
    d.update(
        code=code,
        title=title,
        short=ask("Короткое название для реестра и превью", old.get("short") or title),
        kind=ask("Вид документа", old.get("kind", "Аналитическая справка")),
        subtitle=ask("Подзаголовок с обложки (Enter — без него)", old.get("subtitle", "")),
        client=ask("Заказчик (Enter — нет)", old.get("client", "")),
        date=ask("Дата редакции, ГГГГ-ММ-ДД", old.get("date") or datetime.date.today().isoformat()),
        edition=ask("Редакция", old.get("edition", "1.0")),
        summary=ask("О чём документ, 1–2 предложения (это же текст превью в Telegram)", old.get("summary", "")),
        post=ask("Ссылка на пост в канале (Enter — потом)", old.get("post", "")),
        pdf=code + ".pdf",
        pages=int(info.get("Pages", old.get("pages", 0))),
        size=info["size"],
    )
    if not d["summary"]:
        sys.exit("без описания не добавляю: оно идёт в превью ссылки")
    d.setdefault("about", [d["summary"]])

    dirp = os.path.join(ROOT, "docs", slug(code))
    os.makedirs(dirp, exist_ok=True)
    shutil.copyfile(pdf, os.path.join(dirp, d["pdf"]))
    docs = [x for x in docs if x["code"] != code] + [d]
    save(DOCS_JSON, docs)
    doc_images(d)
    build()

    url = load(SITE_JSON, {})["base_url"].rstrip("/") + "/docs/%s/" % slug(code)
    print("\nГотово. Адрес после публикации: %s" % url)
    print("Аннотацию, «Главное» и «Что не вошло» можно дописать в _content/docs.json (поля about, points, limits),")
    print("затем: python3 ubv.py build. Посмотреть: python3 ubv.py preview. Выложить: python3 ubv.py publish")


def cmd_link(code, url):
    docs = load(DOCS_JSON, [])
    d = next((x for x in docs if x["code"] == code.upper()), None)
    if not d:
        sys.exit("нет документа %s" % code)
    d["post"] = url
    save(DOCS_JSON, docs)
    build()


def cmd_preview():
    print("http://localhost:8090 — остановить: Ctrl+C")
    os.chdir(ROOT)
    subprocess.run([sys.executable, "-m", "http.server", "8090"])


def cmd_publish(msg):
    build()
    os.chdir(ROOT)
    if subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True).returncode:
        sys.exit("нет репозитория на GitHub — см. п. 1 гайда, шаги 2–3 (00_Гайд_GitHub_Pages.md)")
    subprocess.run(["git", "add", "-A"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("изменений нет")
        return
    subprocess.run(["git", "commit", "-m", msg or "Обновление сайта " + datetime.date.today().isoformat()], check=True)
    subprocess.run(["git", "push"], check=True)
    print("отправлено — сайт обновится примерно через минуту")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
    elif argv[0] == "add" and len(argv) == 2:
        cmd_add(argv[1])
    elif argv[0] == "web" and len(argv) == 2:
        cmd_web(argv[1])
    elif argv[0] == "cms":
        import cms
        cms.serve(ROOT, build)
    elif argv[0] == "link" and len(argv) == 3:
        cmd_link(argv[1], argv[2])
    elif argv[0] == "build":
        build(images="--images" in argv)
    elif argv[0] == "preview":
        cmd_preview()
    elif argv[0] == "publish":
        cmd_publish(" ".join(argv[1:]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
