"""Разбор XML из pdftohtml -xml: страницы, шрифты, строки. Общая часть для doc_web.py."""
import html
import re
from dataclasses import dataclass, field


@dataclass
class Seg:
    top: int
    left: int
    width: int
    height: int
    font: str
    size: int
    family: str
    color: str
    bold: bool
    italic: bool
    text: str

    @property
    def right(self):
        return self.left + self.width

    @property
    def key(self):
        return (self.size, self.family, self.color, self.bold, self.italic)


@dataclass
class Line:
    page: int
    top: int
    segs: list = field(default_factory=list)

    @property
    def left(self):
        return min(s.left for s in self.segs)

    @property
    def right(self):
        return max(s.right for s in self.segs)

    @property
    def bottom(self):
        return max(s.top + s.height for s in self.segs)

    @property
    def text(self):
        return join_segs(self.segs)

    def main(self):
        """Шрифт, которым набрана большая часть строки."""
        w = {}
        for s in self.segs:
            if s.text.strip():
                w[s.key] = w.get(s.key, 0) + len(s.text)
        return max(w, key=w.get) if w else self.segs[0].key


def join_segs(segs):
    out = ""
    prev = None
    for s in sorted(segs, key=lambda s: s.left):
        if prev is not None:
            gap = s.left - prev.right
            if gap > max(2, s.size * 0.18) and not out.endswith(" ") and not s.text.startswith(" "):
                out += " "
        out += s.text
        prev = s
    return out


def load(path):
    x = open(path, encoding="utf-8").read()
    fonts = {m.group(1): (int(m.group(2)), m.group(3).split("+")[-1], m.group(4))
             for m in re.finditer(r'<fontspec id="(\d+)" size="(-?\d+)" family="([^"]+)" color="([^"]+)"', x)}
    pages = []
    for pm in re.finditer(r'<page number="(\d+)"[^>]*height="(\d+)" width="(\d+)">(.*?)</page>', x, re.S):
        segs = []
        for m in re.finditer(r'<text top="(-?\d+)" left="(-?\d+)" width="(\d+)" height="(\d+)" font="(\d+)">(.*?)</text>', pm.group(4), re.S):
            raw = m.group(6)
            bold, italic = "<b>" in raw, "<i>" in raw
            txt = html.unescape(re.sub(r"<[^>]+>", "", raw))
            size, fam, col = fonts[m.group(5)]
            segs.append(Seg(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5), size, fam, col, bold, italic, txt))
        pages.append((int(pm.group(1)), int(pm.group(2)), int(pm.group(3)), segs))
    return pages


def lines_of(pno, segs, tol=3):
    """Сегменты -> строки: близкие по вертикали (по базовой линии) объединяются."""
    segs = sorted(segs, key=lambda s: (s.top + s.height, s.left))
    lines = []
    for s in segs:
        base = s.top + s.height
        for ln in lines:
            lb = max(t.top + t.height for t in ln.segs)
            if abs(lb - base) <= tol and not overlaps(ln, s):
                ln.segs.append(s)
                ln.top = min(ln.top, s.top)
                break
        else:
            lines.append(Line(pno, s.top, [s]))
    for ln in lines:
        ln.segs.sort(key=lambda s: s.left)
    return sorted(lines, key=lambda l: (l.top, l.left))


def overlaps(ln, s):
    return any(not (s.left >= t.right - 1 or s.right <= t.left + 1) for t in ln.segs)


if __name__ == "__main__":
    import sys
    pages = load(sys.argv[1])
    want = [int(p) for p in sys.argv[2].split(",")]
    for pno, h, w, segs in pages:
        if pno not in want:
            continue
        print(f"=== page {pno} {w}x{h}")
        for ln in lines_of(pno, segs):
            k = ln.main()
            print(f"{ln.top:5d} {ln.left:4d}-{ln.right:4d} {k[0]:>2}{k[1][:6]:>7} {k[2]} {'B' if k[3] else ' '}{'I' if k[4] else ' '} | {ln.text[:110]}")
