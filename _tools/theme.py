# -*- coding: utf-8 -*-
"""Тема сайта UBVPROJECT (вариант A «Подвес»): HTML из _content/*.json.

Стили и скрипты — обычные файлы assets/site.css и assets/site.js. Пиктограммы технологий — _tools/icons/*.svg
(тело SVG с классами ролей цвета: f-i/s-i — основной, f-a/s-a — акцент, f-b — фон, s-m — вспомогательный).
"""
import datetime
import html
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "_tools", "icons")
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Michroma&family=Unbounded:wght@400;500;600&display=swap">')
THEME_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 7a5 5 0 0 1 0 10Z" fill="currentColor"/></svg>'


def esc(s):
    return html.escape(str(s or ""), quote=True)


def ru_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%d.%m.%Y")
    except Exception:
        return esc(iso)


def icon(slug):
    p = os.path.join(ICONS, f"{slug}.svg")
    body = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return f'<svg viewBox="0 0 200 200" class="sym" aria-hidden="true">{body}</svg>'


def icon_names():
    p = os.path.join(ICONS, "icons.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


# ------------------------------------------------------------------ каркас
def head(c, *, root, path, title, description, og_image, og_type="website"):
    s = c["site"]
    base = s["base_url"].rstrip("/") + "/"
    return (f'<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(description)}">'
            f'<link rel="canonical" href="{base}{path}">'
            f'<meta property="og:site_name" content="UBVPROJECT"><meta property="og:locale" content="ru_RU"><meta property="og:type" content="{og_type}">'
            f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">'
            f'<meta property="og:url" content="{base}{path}"><meta property="og:image" content="{base}{og_image}">'
            f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
            f'<meta name="theme-color" content="#0D0E10"><link rel="icon" href="{root}assets/logo.svg" type="image/svg+xml">'
            f'{FONTS}<link rel="stylesheet" href="{root}assets/site.css"></head>')


def header(c, root, spa):
    s = c["site"]
    if spa:
        tabs = "".join(f'<button type="button" data-tab-btn="{esc(n["id"])}">{esc(n["label"])}</button>' for n in s["nav"])
        brand_href = 'href="#home" data-go="home"'
    else:
        tabs = "".join(f'<a class="tablink" href="{root}#{esc(n["id"])}">{esc(n["label"])}</a>' for n in s["nav"])
        brand_href = f'href="{root}"'
    return (f'<header class="top"><div class="wrap">'
            f'<a class="brand" {brand_href} aria-label="{esc(s["brand"]["word"])} — на главную"><svg viewBox="0 0 200 200" class="sym" data-gimbal=\'{{"w":9,"speed":14,"hover":false,"hidden":false}}\'></svg><span class="word">{esc(s["brand"]["word"])}</span></a>'
            f'<nav class="tabs" aria-label="Разделы">{tabs}<i class="ink"></i></nav>'
            f'<div class="tools"><button class="icon-btn" type="button" data-act="theme" aria-label="Сменить тему">{THEME_ICON}</button>'
            f'<a class="tg" href="{esc(s["telegram"]["url"])}" rel="noopener">{esc(s["telegram"].get("button", "Канал ↗"))}</a></div></div></header>')


def footer(c):
    b = c["site"]["brand"]
    return (f'<footer><div class="wrap"><span class="word">{esc(b["word"])}</span><span>{esc(b["line"])}</span>'
            f'<span>{datetime.date.today().year}</span><span>{esc(b.get("footer_note", ""))}</span>'
            f'<span style="margin-left:auto"><a href="{esc(c["site"]["telegram"]["url"])}" rel="noopener">{esc(c["site"]["telegram"]["name"])}</a></span></div></footer>')


def shell(c, *, root, path, title, description, og_image, main, spa=False, og_type="website"):
    return (head(c, root=root, path=path, title=title, description=description, og_image=og_image, og_type=og_type)
            + f'<body>{header(c, root, spa)}<main>{main}</main>{footer(c)}<script src="{root}assets/site.js"></script></body></html>\n')


# ------------------------------------------------------------------ блоки
def sec_h(label, title, lead=""):
    p = f"<p>{esc(lead)}</p>" if lead else ""
    return f'<div class="sec-h reveal"><span class="label">{esc(label)}</span><h2>{esc(title)}</h2>{p}</div>'


def hero(c):
    h = c["home"]
    facts = "".join(f'<div><b>{esc(f["value"])}</b><span>{esc(f["label"])}</span></div>' for f in h["facts"])
    ticks = "".join(
        f'<path d="M{100 + 96 * math.cos(math.radians(a)):.1f} {100 + 96 * math.sin(math.radians(a)):.1f}'
        f'L{100 + (90 if a % 30 else 86) * math.cos(math.radians(a)):.1f} {100 + (90 if a % 30 else 86) * math.sin(math.radians(a)):.1f}"/>'
        for a in range(0, 360, 6))
    title = "".join(f"<span><em>{esc(t)}</em></span>" for t in h["title"])
    return (f'<div class="heroA"><div class="wrap"><div><div class="kick"><i></i><span class="label">{esc(h["kicker"])}</span></div>'
            f'<h1>{title}</h1><p class="lead">{esc(h["lead"])}</p><div class="facts num">{facts}</div></div>'
            f'<div class="stage"><div class="halo"></div><svg class="ticks sym" viewBox="0 0 200 200" aria-hidden="true"><g class="s-m" stroke-width=".6" fill="none">{ticks}</g></svg>'
            f'<svg viewBox="0 0 200 200" class="sym" role="img" aria-label="Знак UBVPROJECT — карданов подвес" data-gimbal=\'{{"w":3.4,"speed":10,"R":74}}\'></svg>'
            f'<span class="wm word">{esc(h.get("stage_caption", ""))}</span></div></div></div>'
            f'<div class="bigword" aria-hidden="true">{esc(c["site"]["brand"]["word"])}</div>')


def opt_block(c):
    o = c["optimum"]

    def items(lst):
        return "".join(f'<li><b>{esc(i["name"])}</b><span>{esc(i["text"])}</span><i class="bar" style="--v:{float(i.get("value", .5)):.2f}"></i></li>' for i in lst)
    r = o["result"]
    title = esc(r["title"])
    if r.get("accent") and r["accent"] in r["title"]:
        title = esc(r["title"]).replace(esc(r["accent"]), f'<em>{esc(r["accent"])}</em>', 1)
    return (f'<div class="opt reveal"><div class="min"><div class="dir"><i>↓</i>MINIMUM</div><ul>{items(o["min"])}</ul></div>'
            f'<div class="max"><div class="dir"><i>↑</i>MAXIMUM</div><ul>{items(o["max"])}</ul></div>'
            f'<div class="result"><b>{title}</b><span>{esc(r["text"])}</span></div></div>')


def techs(c, n=None):
    items = c["tech"]["items"][:n] if n else c["tech"]["items"]
    return '<div class="techs">' + "".join(
        f'<div class="tech reveal">{icon(i["icon"])}<b>{esc(i["title"])}</b><p>{esc(i["text"])}</p></div>' for i in items) + "</div>"


def news_list(c, n=None, home=False):
    items = sorted(c["news"]["items"], key=lambda x: x["date"], reverse=True)
    if home:
        items = [x for x in items if x.get("home", True)]
    items = items[:n] if n else items
    out = []
    for x in items:
        more = f' <a class="more" href="{esc(x["link"])}">Подробнее →</a>' if x.get("link") else ""
        out.append(f'<article class="reveal"><time>{ru_date(x["date"])}</time><span class="tag">{esc(x["tag"])}</span>'
                   f'<div><h3>{esc(x["title"])}</h3></div><p>{esc(x["text"])}{more}</p></article>')
    return '<div class="news">' + "".join(out) + "</div>"


def doc_cards(c, root=""):
    out = []
    for d in sorted(c["docs"], key=lambda d: d["code"], reverse=True):
        href = f'{root}docs/{d["code"].lower()}/'
        img = d.get("image")
        pic = f'<div class="pic"><img src="{root}{esc(img)}" alt="{esc(d["code"])} — {esc(d["short"])}" loading="lazy"></div>' if img else '<div class="pic"></div>'
        read = "Читать на сайте →" if d.get("web") else "Открыть →"
        out.append(f'<div class="doccard reveal">{pic}<div class="txt"><code>{esc(d["code"])}</code>'
                   f'<span class="label">{esc(d["kind"])} · редакция {esc(d["edition"])} · {ru_date(d["date"])}</span>'
                   f'<h3>{esc(d["title"])}</h3><p>{esc(d["summary"])}</p>'
                   f'<div class="btns"><a class="btn solid" href="{href}">{read}</a><a class="btn" href="{href}{esc(d["pdf"])}">PDF</a></div></div></div>')
    return "".join(out) or '<p class="lead">Документов пока нет.</p>'


def pic(img, alt="", root=""):
    """Картинка или пара для тем: строка — одна, {"dark": …, "light": …} — по теме сайта."""
    if isinstance(img, dict):
        return (f'<img class="t-dark" src="{root}{esc(img["dark"])}" alt="{esc(alt)}" loading="lazy">'
                f'<img class="t-light" src="{root}{esc(img["light"])}" alt="{esc(alt)}" loading="lazy">')
    return f'<img src="{root}{esc(img)}" alt="{esc(alt)}" loading="lazy">'


def own_cards(p):
    """Собственные изделия UbV: карточка во вкладке «Проекты» -> страница projects/<slug>/."""
    out = []
    for pr in p.get("own", []):
        dl = f'<a class="btn" href="{esc(pr["path"])}{esc(pr["download"]["file"])}">{esc(pr["download"]["label"])}</a>' if pr.get("download") else ""
        out.append(f'<div class="doccard reveal"><div class="pic">{pic(pr["image"], pr["name"])}</div>'
                   f'<div class="txt"><code>{esc(pr["name"])}</code><span class="label">{esc(pr["who"])} · {ru_date(pr["date"])}</span>'
                   f'<h3>{esc(pr["title"])}</h3><p>{esc(pr["about"])}</p>'
                   f'<div class="btns"><a class="btn solid" href="{esc(pr["path"])}">Страница проекта →</a>{dl}</div></div></div>')
    return "".join(out)


# ------------------------------------------------------------------ главная (все вкладки)
def home_page(c):
    h, o, t, n, p, a, s = c["home"], c["optimum"], c["tech"], c["news"], c["projects"], c["about"], c["site"]
    bl = h["blocks"]
    tg = s["telegram"]
    pol = "".join(f'<div class="reveal"><span class="n">{i + 1:02d}</span><b>{esc(x["title"])}</b><p>{esc(x["text"])}</p></div>' for i, x in enumerate(a["policy"]))
    draft = ' · <span class="draft">черновик</span>' if a.get("draft") else ""
    partners = []
    for pr in p["partners"]:
        gal = "".join(f'<figure><img src="{esc(g)}" alt="" loading="lazy"></figure>' for g in pr.get("gallery", []))
        link = f'<a class="btn solid" href="{esc(pr["path"])}">Страница проекта →</a>' if pr.get("path") else ""
        partners.append(
            f'<div class="doccard reveal"><div class="pic"><img src="{esc(pr["image"])}" alt="{esc(pr["name"])}" loading="lazy"></div>'
            f'<div class="txt"><code>{esc(pr["name"])}</code><span class="label">{esc(pr["who"])}</span><h3>{esc(pr["title"])}</h3><p>{esc(pr["about"])}</p>'
            f'<div class="btns">{link}<button class="btn" data-go="projects">← Все проекты</button></div></div></div>'
            + (f'<div class="gal reveal"><figure><img src="{esc(pr["image"])}" alt="" loading="lazy"></figure>{gal}</div>' if gal else ""))
    dp = s.get("docs_page", {})
    soon = (f'<div class="soon reveal"><div class="pic"><img class="shade t-dark" src="{esc(p["soon_image"])}" alt=""><img class="shade t-light" src="{esc(p["soon_image_light"])}" alt=""><img class="lineart" src="{esc(p["soon_lineart"])}" alt=""></div>'
            f'<div class="txt"><span class="label">{esc(p["soon_label"])}</span><p>{esc(p["soon"])}</p><span class="label">{esc(p["soon_hint"])}</span></div></div>')
    main = f"""
<section data-tab="home">{hero(c)}
  <div class="wrap sec">{sec_h(bl["principle_label"], o["title"], o["lead"])}{opt_block(c)}</div>
  <div class="wrap sec">{sec_h(bl["tech_label"], bl["tech_title"], bl["tech_lead"])}{techs(c, 6)}
    <div class="btns reveal" style="margin-top:22px"><button class="btn" data-go="tech">Все технологии →</button></div></div>
  <div class="wrap sec">{sec_h(bl["docs_label"], bl["docs_title"])}{doc_cards(c)}</div>
  <div class="wrap sec">{sec_h(bl["news_label"], bl["news_title"])}{news_list(c, int(bl.get("news_count", 2)), home=True)}
    <div class="btns reveal" style="margin-top:22px"><button class="btn" data-go="news">Все новости →</button></div></div>
</section>
<section data-tab="news"><div class="wrap sec">{sec_h("Новости", n["title"])}{news_list(c)}</div></section>
<section data-tab="projects"><div class="wrap sec">{sec_h("Проекты", p["title"], p.get("lead", "") if p.get("own") else "")}
  {own_cards(p) or soon}
  <div class="powered reveal"><div><span class="pb">{esc(p["partners_title"])}</span><b>{esc(p["partners_title"])}</b></div><button class="btn solid" data-go="powered">Открыть →</button></div>
</div></section>
<section data-tab="powered"><div class="wrap sec">{sec_h("Проекты", p["partners_title"], p["partners_lead"])}{"".join(partners)}</div></section>
<section data-tab="docs"><div class="wrap sec">{sec_h("Документы", dp.get("title", "Документы"), dp.get("lead", ""))}{doc_cards(c)}</div></section>
<section data-tab="tech"><div class="wrap sec">{sec_h("Технологии", t["title"], t["lead"])}{techs(c)}</div>
  <div class="wrap sec">{sec_h("Принцип", o["title"], o["lead"])}{opt_block(c)}</div></section>
<section data-tab="about"><div class="wrap sec">{sec_h(s["nav"][-1]["label"], a["title"])}
  <div class="about"><div class="txt reveal">{"".join(f"<p>{esc(x)}</p>" for x in a["text"])}</div>
  <div><span class="label" style="display:block;margin-bottom:12px">{esc(a["policy_title"])}{draft}</span><div class="policy">{pol}</div></div></div>
  <div class="channel reveal"><div><span class="label">Telegram</span><b>{esc(tg["title"])}</b></div><a class="btn solid" href="{esc(tg["url"])}" rel="noopener">{esc(tg["name"])} ↗</a></div>
</div></section>"""
    return shell(c, root="", path="", title=s["seo"]["title"], description=s["seo"]["description"],
                 og_image="assets/og/home.png", main=main, spa=True)


# ------------------------------------------------------------------ прочие страницы
def doc_landing(c, d):
    """Страница документа без веб-версии: карточка, аннотация, главное, ограничения, PDF."""
    root = "../../"
    about = "".join(f"<p class='lead' style='margin-bottom:12px'>{esc(x)}</p>" for x in d.get("about", [d["summary"]]))
    pts = ("<h2 style='margin-top:40px;font-size:24px'>Главное</h2><ul class='dash'>" + "".join(f"<li>{esc(x)}</li>" for x in d["points"]) + "</ul>") if d.get("points") else ""
    lim = ("<h2 style='margin-top:30px;font-size:24px'>Что не вошло и ограничения</h2><ul class='dash'>" + "".join(f"<li>{esc(x)}</li>" for x in d["limits"]) + "</ul>") if d.get("limits") else ""
    post = f'<a class="btn" href="{esc(d["post"])}" rel="noopener">Пост в канале ↗</a>' if d.get("post") else ""
    main = (f'<section class="on"><div class="wrap page"><span class="label">{esc(d["kind"])} · {esc(d["code"])} · редакция {esc(d["edition"])} · {ru_date(d["date"])}</span>'
            f'<h1>{esc(d["title"])}</h1>{about}<div class="btns"><a class="btn solid" href="{esc(d["pdf"])}">Скачать PDF · {esc(d.get("size", ""))}</a>{post}</div>{pts}{lim}</div></section>')
    return shell(c, root=root, path=f'docs/{d["code"].lower()}/', title=f'{d["code"]} · {d["short"]} — UBVPROJECT',
                 description=d["summary"], og_image=f'docs/{d["code"].lower()}/og.png', main=main, og_type="article")


def project_page(c, pr):
    """Страница собственного изделия: шапка, кадр, числа, галерея, пакет, печать, ограничения, лицензия."""
    root = "../../"
    g = pr["page"]
    dl = pr.get("download")
    btn = (f'<a class="btn solid" href="{esc(dl["file"])}">{esc(dl["label"])} · {esc(dl.get("size", ""))}</a>' if dl else "")
    post = f'<a class="btn" href="{esc(pr["post"])}" rel="noopener">Пост в канале ↗</a>' if pr.get("post") else ""
    facts = "".join(f'<div><b>{esc(f["value"])}</b><span>{esc(f["label"])}</span></div>' for f in g["facts"])
    lead = "".join(f'<p class="lead">{esc(x)}</p>' for x in g["lead"])
    gal = "".join(f'<figure class="{esc(x.get("cls", ""))}">{pic(x["img"], x.get("cap", ""), root)}'
                  f'<figcaption>{esc(x.get("cap", ""))}</figcaption></figure>' for x in g["gallery"])
    rows = "".join(f'<tr><td><code>{esc(r[0])}</code></td><td>{esc(r[1])}</td><td>{esc(r[2])}</td></tr>' for r in g["files"])

    def block(title, items):
        return f'<h2>{esc(title)}</h2><ul class="dash">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"
    sections = "".join(block(b["title"], b["items"]) for b in g["blocks"])
    main = (f'<section class="on"><div class="wrap page pj">'
            f'<span class="label">{esc(pr["who"])} · {ru_date(pr["date"])}</span><h1>{esc(g["h1"])}</h1>{lead}'
            f'<div class="btns">{btn}{post}</div>'
            f'<figure class="pj-hero reveal">{pic(g["hero"], g["h1"], root)}</figure>'
            f'<div class="pj-facts num reveal">{facts}</div>'
            f'<h2>{esc(g["idea_title"])}</h2>' + "".join(f"<p class='pj-p'>{esc(x)}</p>" for x in g["idea"]) +
            f'<div class="pj-gal reveal">{gal}</div>'
            f'<h2>{esc(g["files_title"])}</h2><p class="pj-p">{esc(g["files_lead"])}</p>'
            f'<div class="pj-table"><table><thead><tr><th>Файл</th><th>Деталь</th><th>Печать</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'{sections}<p class="pj-lic label">{esc(g["license"])}</p>'
            f'<div class="btns">{btn}<a class="btn" href="{root}#projects">← Все проекты</a></div></div></section>')
    return shell(c, root=root, path=pr["path"], title=f'{pr["name"]} — {pr["title"]} · UBVPROJECT',
                 description=pr["about"], og_image=pr["path"] + "og.png", main=main, og_type="article")


def docs_redirect(c):
    base = c["site"]["base_url"].rstrip("/") + "/"
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Документы — UBVPROJECT</title>'
            f'<link rel="canonical" href="{base}#docs"><meta http-equiv="refresh" content="0; url=../#docs"></head>'
            f'<body><a href="../#docs">Документы UBVPROJECT</a></body></html>\n')


def not_found(c):
    main = ('<section class="on"><div class="wrap page"><div class="nf">404</div><h1>Такой страницы нет</h1>'
            '<p class="lead">Возможно, адрес изменился после обновления сайта.</p><div class="btns"><a class="btn solid" href="/">На главную →</a></div></div></section>')
    return shell(c, root="/", path="404.html", title="Страница не найдена — UBVPROJECT", description=c["site"]["seo"]["description"],
                 og_image="assets/og/home.png", main=main)
