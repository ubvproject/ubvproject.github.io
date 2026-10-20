#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сайт UbVProject: добавление документов и сборка страниц.

    python3 ubv.py add путь/к/файлу.pdf     добавить документ (или новую редакцию) — спросит код, название, аннотацию
    python3 ubv.py link UBV-AS-2026-01 URL   привязать пост в канале к документу
    python3 ubv.py build                     пересобрать все страницы из _content/*.json
    python3 ubv.py preview                   открыть сайт локально: http://localhost:8090
    python3 ubv.py publish ["сообщение"]     собрать, закоммитить и отправить на GitHub

Данные — _content/site.json (главная) и _content/docs.json (документы), шаблоны — _tools/templates/.
Нужны: Google Chrome (картинки превью) и poppler (pdfinfo, pdftoppm): brew install poppler.
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


def page(site, *, root, path, title, og_title, description, og_image, content, og_type="website", nav_docs=""):
    tg = site["telegram"]
    return fill(tpl("base.html"), root=root, title=esc(title), og_title=esc(og_title), description=esc(description),
                url=site["base_url"].rstrip("/") + "/" + path, og_image=site["base_url"].rstrip("/") + "/" + og_image,
                og_type=og_type, nav_docs=nav_docs, logo=logo(), tg_url=esc(tg["url"]), tg_name=esc(tg["name"]),
                year=datetime.date.today().year, content=content)


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def registry(docs, root):
    if not docs:
        return '<p class="note">Документов пока нет.</p>'
    rows = []
    for d in docs:
        href = "%sdocs/%s/" % (root, slug(d["code"]))
        rows.append('<tr><td class="code">%s</td><td class="ttl"><a href="%s">%s</a><span class="kd">%s</span></td>'
                    '<td class="date">%s</td><td class="pdf"><a href="%s%s">PDF ↓</a></td></tr>'
                    % (esc(d["code"]), href, esc(d["short"]), esc(d["kind"] + (" · " + d["client"] if d.get("client") else "")),
                       ru_date(d["date"]), href, esc(d["pdf"])))
    return ('<table class="reg"><thead><tr><th>Код</th><th>Название</th><th class="date">Дата</th><th></th></tr></thead>'
            "<tbody>%s</tbody></table>" % "".join(rows))


def projects_table(projects, root):
    """Проекты — готовые статичные страницы в projects/<slug>/, генератор их не трогает, только ссылается"""
    if not projects:
        return ""
    rows = "".join('<tr><td class="code">%s</td><td class="ttl"><a href="%s%s">%s</a><span class="kd">%s</span></td>'
                   '<td class="date">%s</td><td class="pdf"><a href="%s%s">Открыть →</a></td></tr>'
                   % (esc(p["name"]), root, esc(p["path"]), esc(p["title"]), esc(p["kind"]), ru_date(p["date"]),
                      root, esc(p["path"])) for p in projects)
    return ('<section>\n  <h2 class="h">Проекты</h2>\n  <table class="reg"><thead><tr><th>Проект</th><th>Название</th>'
            '<th class="date">Дата</th><th></th></tr></thead><tbody>%s</tbody></table>\n</section>' % rows)


def dash(items):
    return '<ul class="dash">%s</ul>' % "".join("<li>%s</li>" % esc(i) for i in items)


# ---------- сборка ----------

def build(images=False):
    site, docs = load(SITE_JSON, {}), sorted(load(DOCS_JSON, []), key=lambda d: d["code"], reverse=True)
    projects = sorted(load(PROJECTS_JSON, []), key=lambda p: p["date"], reverse=True)
    tg = site["telegram"]

    metrics = []
    for m in site.get("metrics", []):
        if m.get("auto") == "docs":
            n = len(docs)
            m = {"value": str(n), "label": plural(n, "документ", "документа", "документов") + " UBV-AS"}
        metrics.append('<div><div class="big">%s</div><div class="lbl">%s</div></div>' % (esc(m["value"]), esc(m["label"])))

    home = fill(tpl("home.html"), headline=esc(site["headline"]), lead=esc(site["lead"]), metrics="".join(metrics),
                registry=registry(docs, ""), projects=projects_table(projects, ""), tg_name=esc(tg["name"]), tg_title=esc(tg["title"]),
                tg_about=esc(tg["about"]), tg_url=esc(tg["url"]))
    write("index.html", page(site, root="", path="", title="UbVProject — программирование и конструкция БАС",
                             og_title="UbVProject — программирование и конструкция БАС", description=site["lead"],
                             og_image="assets/og/home.png", content=home))

    write("docs/index.html", page(site, root="../", path="docs/", title="Документы UBV-AS — UbVProject",
                                  og_title="Документы UBV-AS", description="Справки и пособия UbVProject: реестр с PDF.",
                                  og_image="assets/og/home.png", content=fill(tpl("docs.html"), root="../",
                                  registry=registry(docs, "../")), nav_docs="on"))

    write("404.html", page(site, root="/", path="404.html", title="Страница не найдена — UbVProject",
                           og_title="UbVProject", description=site["lead"], og_image="assets/og/home.png",
                           content=fill(tpl("404.html"), root="/")))

    for d in docs:
        build_doc(site, d)

    og_home = os.path.join(ROOT, "assets", "og", "home.png")
    if images or not os.path.exists(og_home):
        render_og(og_home, kind="Документы и проекты", title=site["headline"], meta='<span>%s</span>' % esc(tg["name"]))
    for d in docs:
        dirp = os.path.join(ROOT, "docs", slug(d["code"]))
        if images or not os.path.exists(os.path.join(dirp, "og.png")):
            doc_images(d)

    urls = [""] + ["docs/"] + ["docs/%s/" % slug(d["code"]) for d in docs] + [p["path"] for p in projects]
    base = site["base_url"].rstrip("/") + "/"
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join("  <url><loc>%s%s</loc></url>\n" % (base, u) for u in urls) + "</urlset>\n")
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % base)
    print("собрано: главная, реестр, %d %s" % (len(docs), plural(len(docs), "документ", "документа", "документов")))


def build_doc(site, d):
    s, root = slug(d["code"]), "../../"
    kv = [("Обозначение", "<code>%s</code>, редакция %s" % (esc(d["code"]), esc(d["edition"]))),
          ("Дата", ru_date(d["date"]))]
    if d.get("client"):
        kv.append(("Подготовлено", "по запросу " + esc(d["client"])))
    kv.append(("Объём", "%d %s, PDF %s" % (d["pages"], plural(d["pages"], "страница", "страницы", "страниц"), d["size"])))
    post = ('<a class="btn ghost" href="%s" rel="noopener">Пост в канале ↗</a>' % esc(d["post"])) if d.get("post") else ""
    limits = ""
    if d.get("limits"):
        limits = '<aside class="callout"><div class="h">Что не вошло и ограничения</div>%s</aside>' % dash(d["limits"])
    content = fill(tpl("doc.html"), root=root, code=esc(d["code"]), kind=esc(d["kind"]), title=esc(d["title"]),
                   subtitle=('<p class="sub">%s</p>' % esc(d["subtitle"])) if d.get("subtitle") else "",
                   pdf=esc(d["pdf"]), size=esc(d["size"]), post_btn=post,
                   kv="".join('<tr><td class="k">%s</td><td>%s</td></tr>' % r for r in kv),
                   about="".join("<p>%s</p>" % esc(p) for p in d.get("about", [d["summary"]])),
                   points=("<h2>Главное</h2>" + dash(d["points"])) if d.get("points") else "",
                   limits=limits, pages="%d %s" % (d["pages"], plural(d["pages"], "страница", "страницы", "страниц")))
    write("docs/%s/index.html" % s, page(site, root=root, path="docs/%s/" % s, og_type="article",
                                         title="%s · %s — UbVProject" % (d["code"], d["short"]),
                                         og_title="%s · %s" % (d["code"], d["short"]), description=d["summary"],
                                         og_image="docs/%s/og.png" % s, content=content, nav_docs="on"))


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
                        "--allow-file-access-from-files", "--window-size=1200,630", "--screenshot=" + out, "file://" + tmp],
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
