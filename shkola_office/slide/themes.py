"""InterSlide: теми оформлення (власного дизайну ГС «УАІТ») і макети шкільних слайдів.
Елемент має роль (title/body/accent/accent2/card/decor); тема перефарбовує за роллю й ставить свої декор-елементи."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import SIZES, Element, Presentation, Slide


@dataclass
class Theme:
    name: str
    bg: str
    title: str
    body: str
    accent: str
    accent2: str
    card: str                 # тло карток/блоків
    card_text: str
    font: str
    title_font: str
    decor: Callable[[float, float, bool], list[Element]]   # (W, H, титульний?) → декор
    on_accent: str = ""       # текст на акцентних плашках ("" — колір тла)


def _minimal_decor(W: float, H: float, cover: bool) -> list[Element]:
    if cover:
        return [Element("shape", 0, 0, W, H * 0.12, shape="Прямокутник", fill="#135548", role="decor"),
                Element("shape", 0, H * 0.12, W, 6, shape="Прямокутник", fill="#e0a526", role="decor"),
                Element("shape", W * 0.42, H * 0.78, W * 0.16, 5, shape="Прямокутник", fill="#e0a526", role="decor")]
    return [Element("shape", 0, 0, 14, H, shape="Прямокутник", fill="#135548", role="decor"),
            Element("shape", 14, 0, 4, H, shape="Прямокутник", fill="#e0a526", role="decor")]


def _board_decor(W: float, H: float, cover: bool) -> list[Element]:
    wood, b = "#8a5a2b", 16
    out = [Element("shape", 0, 0, W, b, shape="Прямокутник", fill=wood, role="decor"),
           Element("shape", 0, H - b, W, b, shape="Прямокутник", fill=wood, role="decor"),
           Element("shape", 0, 0, b, H, shape="Прямокутник", fill=wood, role="decor"),
           Element("shape", W - b, 0, b, H, shape="Прямокутник", fill=wood, role="decor"),
           Element("shape", W * 0.7, H - b - 10, 46, 10, shape="Скруглений прямокутник", fill="#f4f1e6", role="decor")]
    if cover:
        out.append(Element("shape", W * 0.3, H * 0.62, W * 0.4, 4, shape="Прямокутник", fill="#f2c14e", role="decor"))
    return out


def _svg(W, H, body: str) -> Element:
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:g} {H:g}" width="{W:g}" height="{H:g}">{body}</svg>'
    return Element("image", 0, 0, W, H, s, role="decor")


def _grid_decor(W, H, cover):
    step = 20
    lines = "".join(f'<line x1="{x}" y1="0" x2="{x}" y2="{H:g}"/>' for x in range(step, int(W), step))
    lines += "".join(f'<line x1="0" y1="{y}" x2="{W:g}" y2="{y}"/>' for y in range(step, int(H), step))
    body = f'<g stroke="#cfe0f3" stroke-width="1">{lines}</g>' +         f'<line x1="{W - 40:g}" y1="0" x2="{W - 40:g}" y2="{H:g}" stroke="#e98a84" stroke-width="2"/>'
    return [_svg(W, H, body)]


def _nature_decor(W, H, cover):
    hills = (f'<ellipse cx="{W * .2:g}" cy="{H + 40:g}" rx="{W * .45:g}" ry="{90 if cover else 46}" fill="#b9d89a"/>'
             f'<ellipse cx="{W * .85:g}" cy="{H + 50:g}" rx="{W * .4:g}" ry="{110 if cover else 56}" fill="#8fc06a"/>')
    leaf = lambda x, y, r, c: (f'<path transform="translate({x:g},{y:g}) rotate({r})" d="M0 0C10-26 40-30 60-24 54 0 30 14 0 0z" '
                               f'fill="{c}"/><path transform="translate({x:g},{y:g}) rotate({r})" d="M0 0L52-20" '
                               f'stroke="#f4f8ec" stroke-width="2"/>')
    body = hills + leaf(W - 90, 60, -20, "#6aa84f") + leaf(W - 60, 40, 30, "#8fc06a")
    if cover:
        body += leaf(40, H - 150, -40, "#6aa84f") + f'<circle cx="{W - 140:g}" cy="70" r="26" fill="#f2c94c"/>'
    return [_svg(W, H, body)]


def _space_decor(W, H, cover):
    import random as _r
    rnd = _r.Random(7)
    stars = "".join(f'<circle cx="{rnd.uniform(0, W):.0f}" cy="{rnd.uniform(0, H):.0f}" r="{rnd.choice((0.8, 1.2, 1.8))}" '
                    f'fill="#ffffff" opacity="{rnd.uniform(.35, .9):.2f}"/>' for _ in range(110))
    cx, cy, r = (W - 70, H - 60, 80) if cover else (W - 34, 30, 16)
    planet = (f'<circle cx="{cx:g}" cy="{cy:g}" r="{r}" fill="#7c5cff" opacity=".85"/>'
              f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{r * 1.5:g}" ry="{r * .23:g}" '
              f'fill="none" stroke="#ffd66b" stroke-width="3" transform="rotate(-18 {cx:g} {cy:g})"/>')
    return [_svg(W, H, stars + planet)]


def _parchment_decor(W, H, cover):
    body = (f'<rect x="14" y="14" width="{W - 28:g}" height="{H - 28:g}" fill="none" stroke="#8b4a2b" stroke-width="3"/>'
            f'<rect x="22" y="22" width="{W - 44:g}" height="{H - 44:g}" fill="none" stroke="#c99a3c" stroke-width="1.5"/>'
            + "".join(f'<path transform="translate({x:g},{y:g})" d="M0 -9L9 0 0 9-9 0z" fill="#8b4a2b"/>'
                      for x, y in ((22, 22), (W - 22, 22), (22, H - 22), (W - 22, H - 22))))
    return [_svg(W, H, body)]


def _bright_decor(W, H, cover):
    cols = ("#e8573f", "#2fa4e7", "#f7b928", "#3dbb6b", "#a05be0")
    import random as _r
    rnd = _r.Random(3)
    dots = "".join(f'<circle cx="{x:g}" cy="{y:g}" r="{rnd.choice((6, 9, 13))}" fill="{cols[i % 5]}" opacity=".8"/>'
                   for i, (x, y) in enumerate([(rnd.uniform(0, W), rnd.uniform(0, 26)) for _ in range(14)]
                                              + [(rnd.uniform(0, W), H - rnd.uniform(0, 26)) for _ in range(14)]))
    wave = f'<path d="M0 {H - 34:g}q{W / 8:g}-26 {W / 4:g} 0t{W / 4:g} 0 {W / 4:g} 0 {W / 4:g} 0V{H:g}H0z" fill="#ffe0a3"/>'
    return [_svg(W, H, wave + dots)]


THEMES: dict[str, Theme] = {
    "Мінімал ГС": Theme("Мінімал ГС", "#ffffff", "#135548", "#1f2d2a", "#1d7a66", "#e0a526", "#eef5f2", "#1f2d2a",
                        "Segoe UI", "Segoe UI Semibold", _minimal_decor),
    "Класна дошка": Theme("Класна дошка", "#24453a", "#f6f1d8", "#e8efe9", "#f2c14e", "#9fd3c7", "#2f5a4b", "#f6f1d8",
                          "Segoe Print", "Segoe Print", _board_decor),
    "Зошит у клітинку": Theme("Зошит у клітинку", "#fbfdff", "#1f4e8c", "#22303c", "#e2574c", "#2f8f6f", "#eaf2fb",
                              "#22303c", "Segoe UI", "Segoe Print", _grid_decor, "#ffffff"),
    "Природа": Theme("Природа", "#f4f8ec", "#2f5d27", "#273126", "#4e8a3a", "#e0a526", "#e5efd6", "#273126",
                     "Segoe UI", "Segoe UI Semibold", _nature_decor, "#ffffff"),
    "Космос": Theme("Космос", "#0f1b3d", "#ffd66b", "#e6ecff", "#7c5cff", "#ffd66b", "#1d2b5a", "#e6ecff",
                    "Segoe UI", "Segoe UI Semibold", _space_decor, "#0f1b3d"),
    "Пергамент": Theme("Пергамент", "#f3e7c9", "#6b3a1e", "#3b2a1a", "#8b4a2b", "#c99a3c", "#ead8ae", "#3b2a1a",
                       "Georgia", "Georgia", _parchment_decor, "#f3e7c9"),
    "Яскравий для молодших": Theme("Яскравий для молодших", "#fff8e7", "#e8573f", "#2b2b3a", "#2fa4e7", "#f7b928",
                                   "#ffe9c2", "#2b2b3a", "Segoe UI", "Segoe UI Black", _bright_decor, "#ffffff"),
}
DEFAULT_THEME = "Мінімал ГС"


def _ink(fill: str) -> str:
    """Колір тексту на заливці: темний на світлому, білий на темному (контраст)."""
    c = fill.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r ** 2.2 + 0.7152 * g ** 2.2 + 0.0722 * b ** 2.2
    return "#1d2423" if lum > 0.32 else "#ffffff"


def _paint(e: Element, t: Theme) -> None:
    if e.role == "title":
        e.color, e.font = t.title, t.title_font
    elif e.role == "body":
        e.color, e.font = t.body, t.font
    elif e.role in ("accent", "accent2"):
        e.fill = t.accent if e.role == "accent" else t.accent2
        e.line, e.color, e.font = e.fill, (_ink(e.fill) if e.kind == "shape" else t.body), t.font
    elif e.role == "card" or e.role.startswith("opt:"):
        e.fill, e.line, e.color, e.font = t.card, t.card, t.card_text, t.font


def apply_theme(pres: Presentation, name: str) -> None:
    """Перефарбувати всі слайди: тло, ролі, декор теми. Елементи без ролі (додані вручну) не чіпаємо."""
    t = THEMES.get(name, THEMES[DEFAULT_THEME])
    pres.theme, pres.font = t.name, t.font
    W, H = pres.size
    for s in pres.slides:
        s.bg = t.bg
        s.elements = [e for e in s.elements if e.role != "decor"]
        for e in s.elements:
            _paint(e, t)
            if e.role.startswith("lib:"):
                _relib(pres, e, t)
        decorate(pres, s, t)


def decorate(pres: Presentation, s: Slide, t: Theme) -> None:
    """Додати декор теми на початок слайда. SVG-декор приходить у Element.text і переїжджає в media."""
    W, H = pres.size
    els = t.decor(W, H, s.layout in ("Титул", "Тема уроку"))
    for e in els:
        if e.kind == "image" and e.text.startswith("<svg"):
            e.media = pres.add_media(f"theme_{t.name}_{int(W)}x{int(H)}.svg", e.text.encode("utf-8"))
            e.text = ""
    s.elements[:0] = els


def _relib(pres: Presentation, e: Element, t: Theme) -> None:
    from . import library
    it = next((i for i in library.items() if i["id"] == e.role[4:]), None)
    if it:
        e.media = pres.add_media(f"lib_{it['id']}_{t.name}.svg", library.themed_svg(it, t))


def lib_element(pres: Presentation, item: dict, size: float = 140) -> Element:
    """Об'єкт бібліотеки як елемент слайда в кольорах поточної теми (перефарбовується зі зміною теми)."""
    W, H = pres.size
    e = Element("image", (W - size) / 2, (H - size) / 2, size, size, role="lib:" + item["id"])
    _relib(pres, e, THEMES.get(pres.theme or DEFAULT_THEME, THEMES[DEFAULT_THEME]))
    return e


# ---------- макети ----------
def _T(x, y, w, h, text, size, role="body", **kw) -> Element:
    return Element("text", x, y, w, h, text, size, role=role, **kw)


def _card(x, y, w, h, text, size=20, role="card", shape="Скруглений прямокутник", **kw) -> Element:
    return Element("shape", x, y, w, h, text, size, shape=shape, role=role, align=kw.pop("align", "center"), **kw)


def _head(W, text) -> Element:
    return _T(50, 28, W - 100, 64, text, 34, "title", bold=True)


def _layouts(W: float, H: float) -> dict[str, list[Element]]:
    L, top, bw = 50, 110, W - 100
    half = (bw - 30) / 2
    third = (bw - 40) / 3
    return {
        "Титул": [_T(60, H * 0.3, W - 120, 100, "Тема уроку", 46, "title", bold=True, align="center"),
                  _T(60, H * 0.3 + 110, W - 120, 50, "Предмет · клас · дата", 22, align="center")],
        "Тема уроку": [_T(60, H * 0.22, W - 120, 40, "Тема уроку", 22, align="center"),
                       _T(60, H * 0.22 + 50, W - 120, 110, "Назва теми", 44, "title", bold=True, align="center"),
                       _T(60, H * 0.22 + 175, W - 120, 50, "Епіграф або ключове питання", 22, italic=True, align="center")],
        "Мета й результати": [_head(W, "Мета уроку"),
                              _card(L, top, half, H - top - 50, "Мета\n\nЩо ми дізнаємося і навчимося робити", 20, align="left"),
                              _card(L + half + 30, top, half, H - top - 50,
                                    "Очікувані результати\n\n• знатиму…\n• умітиму…\n• зможу пояснити…", 20, align="left")],
        "Пояснення й малюнок": [_head(W, "Пояснення"),
                                _T(L, top, half, H - top - 40, "• Основне правило\n• Приклад\n• Важливо запам'ятати", 22),
                                _card(L + half + 30, top, half, H - top - 50, "Місце для малюнка\n(Додати → Зображення)", 18)],
        "Два стовпці": [_head(W, "Заголовок"),
                        _T(L, top, half, H - top - 40, "• Пункт\n• Пункт\n• Пункт", 22),
                        _T(L + half + 30, top, half, H - top - 40, "• Пункт\n• Пункт\n• Пункт", 22)],
        "Порівняння": [_head(W, "Порівняймо"),
                       _card(L, top, half, 56, "Перше", 24, "accent", bold=True),
                       _card(L + half + 30, top, half, 56, "Друге", 24, "accent2", bold=True),
                       _T(L, top + 70, half, H - top - 110, "• Ознака\n• Ознака\n• Ознака", 22),
                       _T(L + half + 30, top + 70, half, H - top - 110, "• Ознака\n• Ознака\n• Ознака", 22)],
        "Хронологія": [_head(W, "Хронологія"),
                       Element("shape", L, H * 0.52, bw, 6, shape="Прямокутник", role="accent")]
                      + [x for i in range(4) for x in (
                          _card(L + i * (bw - 150) / 3 + 45, H * 0.52 - 27, 60, 60, str(i + 1), 24, "accent2", "Еліпс", bold=True),
                          _T(L + i * (bw - 150) / 3, H * 0.52 + 45, 150, 90, "Рік\nПодія", 18, align="center"))],
        "Кластер": [_head(W, "Кластер"),
                    _card(W / 2 - 110, H / 2 - 20, 220, 90, "Поняття", 26, "accent", "Еліпс", bold=True)]
                   + [_card(x, y, 190, 64, "Ознака", 18) for x, y in
                      ((L, top), (W - L - 190, top), (L, H - 110), (W - L - 190, H - 110))],
        "Підсумок": [_head(W, "Підсумуймо"),
                     *[_card(L + i * (third + 20), top + 10, third, H - top - 70, t, 20, align="left")
                       for i, t in enumerate(("Я дізнався…", "Я навчився…", "Мені цікаво…"))]],
        "Рефлексія": [_head(W, "Як пройшов урок?"),
                      *[_card(L + i * (third + 20), top + 30, third, 160, t, 22, r, "Скруглений прямокутник", bold=True)
                        for i, (t, r) in enumerate((("Усе зрозуміло", "accent"), ("Є питання", "accent2"),
                                                    ("Потрібна допомога", "card")))],
                      _T(L, top + 220, bw, 60, "Оберіть картку й поясніть свій вибір", 22, align="center")],
        "Домашнє завдання": [_head(W, "Домашнє завдання"),
                             _card(L, top, bw, H - top - 50,
                                   "§ …, вправи № …\n\nДля охочих: …\n\nТермін: …", 24, align="left")],
        "Питання": [_head(W, "Питання"),
                    _card(L, top, bw, 90, "Текст запитання?", 26, "accent", bold=True),
                    *[_card(L + (i % 2) * (half + 30), top + 110 + (i // 2) * 90, half, 72, f"{'АБВГ'[i]}) варіант", 22)
                      for i in range(4)]],
    }


LAYOUTS = list(_layouts(960, 540))


def make_slide(layout: str, pres: Presentation) -> Slide:
    W, H = pres.size
    s = Slide(_layouts(W, H)[layout], layout=layout)
    t = THEMES.get(pres.theme or DEFAULT_THEME, THEMES[DEFAULT_THEME])
    s.bg = t.bg
    for e in s.elements:
        _paint(e, t)
    decorate(pres, s, t)
    return s


def new_presentation(theme: str = DEFAULT_THEME, ratio: str = "16:9") -> Presentation:
    p = Presentation(ratio=ratio, theme=theme, font=THEMES[theme].font)
    p.slides.append(make_slide("Титул", p))
    return p
