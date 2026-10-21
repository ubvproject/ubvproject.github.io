# -*- coding: utf-8 -*-
"""Локальная CMS сайта UBVPROJECT: python3 ubv.py cms  ->  http://localhost:8091/admin/

Работает только на этом компьютере (127.0.0.1). Правит _content/*.json, загружает картинки в assets/uploads/,
собирает сайт и показывает предпросмотр. В git ничего не пишет — только показывает список изменённых файлов.
Перед каждым сохранением прежняя версия раздела кладётся в _tools/.cache/history/ (кнопка «Откатить»).
"""
import contextlib
import datetime
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

SECTIONS = ("site", "home", "optimum", "tech", "news", "projects", "about", "docs")
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMG_DIRS = ("assets/v2", "assets/uploads", "projects")
MAX_UPLOAD = 15 * 1024 * 1024
PORT = 8091
LOCK = threading.Lock()


def make_handler(root, build):
    content = os.path.join(root, "_content")
    history = os.path.join(root, "_tools", ".cache", "history")
    admin = os.path.join(root, "_tools", "cms")
    icons = os.path.join(root, "_tools", "icons")

    def section_path(name):
        if name not in SECTIONS:
            raise ValueError("нет такого раздела")
        return os.path.join(content, name + ".json")

    def read_json(p, default):
        if not os.path.exists(p):
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def images():
        out = []
        for d in IMG_DIRS:
            base = os.path.join(root, d)
            for dp, _, fs in os.walk(base):
                for f in sorted(fs):
                    if os.path.splitext(f)[1].lower() in IMG_EXT:
                        out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
        return out

    def icon_lib():
        names = read_json(os.path.join(icons, "icons.json"), {})
        return {k: {"name": v, "svg": open(os.path.join(icons, k + ".svg"), encoding="utf-8").read()} for k, v in names.items()
                if os.path.exists(os.path.join(icons, k + ".svg"))}

    def git_status():
        try:
            br = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True).stdout.strip()
            st = subprocess.run(["git", "status", "--short"], cwd=root, capture_output=True, text=True).stdout
            return {"branch": br, "files": [l for l in st.splitlines() if l.strip()]}
        except Exception as e:
            return {"branch": "?", "files": [], "error": str(e)}

    def history_list(name):
        if not os.path.isdir(history):
            return []
        return sorted(f for f in os.listdir(history) if f.startswith(name + "@"))

    def validate(name, data, old):
        """Тип верхнего уровня и ключи не должны меняться; списки — списками, строки — строками."""
        if type(data) is not type(old):
            raise ValueError("структура раздела изменилась (ожидался %s)" % type(old).__name__)

        def walk(new, ref, path):
            if isinstance(ref, dict) and isinstance(new, dict):
                for k, v in ref.items():
                    if k in new and v is not None and new[k] is not None and type(v) is not type(new[k]) and not (
                            isinstance(v, (int, float)) and isinstance(new[k], (int, float))):
                        raise ValueError(f"{path}{k}: ожидался тип {type(v).__name__}")
                    if k in new:
                        walk(new[k], v, f"{path}{k}.")
            elif isinstance(ref, list) and isinstance(new, list) and ref:
                for i, it in enumerate(new):
                    walk(it, ref[0], f"{path}{i}.")
        walk(data, old, "")
        for m in re.finditer(r'"date":\s*"([^"]*)"', json.dumps(data, ensure_ascii=False)):
            if m.group(1):
                try:
                    datetime.date.fromisoformat(m.group(1))
                except ValueError:
                    raise ValueError("дата «%s»: нужен формат ГГГГ-ММ-ДД" % m.group(1))

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, fmt, *args):
            if "/api/" in (args[0] if args else ""):
                sys.stderr.write("cms: %s\n" % (fmt % args))

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def guard(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                self.send_error(HTTPStatus.FORBIDDEN, "только локально")
                return False
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                self.send_error(HTTPStatus.FORBIDDEN, "чужой источник")
                return False
            return True

        def json_out(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def body(self, limit=2 * 1024 * 1024):
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit:
                self.close_connection = True
                raise ValueError("слишком большой запрос (до %d МБ)" % (limit // 1024 // 1024))
            return self.rfile.read(n)

        # ---------- GET
        def do_GET(self):
            if not self.guard():
                return
            u = urlparse(self.path)
            p = unquote(u.path)
            if p in ("/admin", "/admin/"):
                return self.file(os.path.join(admin, "index.html"))
            if p.startswith("/admin/"):
                f = os.path.normpath(os.path.join(admin, p[len("/admin/"):]))
                if not f.startswith(admin):
                    return self.send_error(404)
                return self.file(f)
            if p == "/api/content":
                data = {k: read_json(section_path(k), [] if k == "docs" else {}) for k in SECTIONS}
                return self.json_out({"content": data, "icons": icon_lib(), "images": images(), "git": git_status(),
                                      "history": {k: len(history_list(k)) for k in SECTIONS}})
            if p == "/api/status":
                return self.json_out({"git": git_status(), "images": images()})
            return super().do_GET()

        def file(self, f):
            if not os.path.isfile(f):
                return self.send_error(404)
            data = open(f, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", (mimetypes.guess_type(f)[0] or "application/octet-stream") + ("; charset=utf-8" if f.endswith((".html", ".js", ".css")) else ""))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        # ---------- PUT / POST
        def do_PUT(self):
            if not self.guard():
                return
            p = unquote(urlparse(self.path).path)
            m = re.fullmatch(r"/api/content/(\w+)", p)
            if not m:
                return self.send_error(404)
            try:
                raw = self.body()                       # тело читаем всегда — иначе браузер получит оборванное соединение
                name = m.group(1)
                path = section_path(name)
                data = json.loads(raw.decode("utf-8"))
                with LOCK:
                    old = read_json(path, [] if name == "docs" else {})
                    validate(name, data, old)
                    os.makedirs(history, exist_ok=True)
                    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    if os.path.exists(path):
                        shutil.copyfile(path, os.path.join(history, f"{name}@{stamp}.json"))
                    tmp = path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                        f.write("\n")
                    os.replace(tmp, path)
                self.json_out({"ok": True, "history": len(history_list(name))})
            except (ValueError, json.JSONDecodeError) as e:
                self.json_out({"ok": False, "error": str(e)}, 400)

        def do_POST(self):
            if not self.guard():
                return
            u = urlparse(self.path)
            p = unquote(u.path)
            try:
                payload = self.body(MAX_UPLOAD)           # тело читаем всегда, до проверок
                if p == "/api/build":
                    buf = io.StringIO()
                    with LOCK, contextlib.redirect_stdout(buf):
                        build()
                    return self.json_out({"ok": True, "log": buf.getvalue().strip(), "git": git_status()})
                if p == "/api/upload":
                    q = dict(x.split("=", 1) for x in u.query.split("&") if "=" in x)
                    name = unquote(q.get("name", "image"))
                    base, ext = os.path.splitext(os.path.basename(name))
                    ext = ext.lower()
                    if ext not in IMG_EXT:
                        raise ValueError("только картинки: png, jpg, webp, gif")
                    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", base.encode("ascii", "ignore").decode()).strip("-")[:60] or "image"
                    data = payload
                    head = data[:12]
                    if not (head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8") or head[:4] == b"RIFF" or head[:3] == b"GIF"):
                        raise ValueError("файл не похож на картинку")
                    d = os.path.join(root, "assets", "uploads")
                    os.makedirs(d, exist_ok=True)
                    fn, i = f"{base}{ext}", 1
                    while os.path.exists(os.path.join(d, fn)):
                        i += 1
                        fn = f"{base}-{i}{ext}"
                    with open(os.path.join(d, fn), "wb") as f:
                        f.write(data)
                    return self.json_out({"ok": True, "path": f"assets/uploads/{fn}", "images": images()})
                m = re.fullmatch(r"/api/restore/(\w+)", p)
                if m:
                    name = m.group(1)
                    hs = history_list(name)
                    if not hs:
                        raise ValueError("нечего откатывать")
                    with LOCK:
                        shutil.copyfile(os.path.join(history, hs[-1]), section_path(name))
                        os.remove(os.path.join(history, hs[-1]))
                    return self.json_out({"ok": True, "data": read_json(section_path(name), {}), "history": len(hs) - 1})
                self.send_error(404)
            except Exception as e:
                self.json_out({"ok": False, "error": str(e)}, 400)

    return H


def serve(root, build, port=PORT, open_browser=True):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root, build))
    url = f"http://localhost:{port}/admin/"
    print(f"Редактор сайта: {url}\nСайт для предпросмотра: http://localhost:{port}/\nПравки сохраняются только на этом компьютере. Остановить: Ctrl+C")
    if open_browser and not os.environ.get("UBV_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")
