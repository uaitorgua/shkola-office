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


THEMES: dict[str, Theme] = {
    "Мінімал ГС": Theme("Мінімал ГС", "#ffffff", "#135548", "#1f2d2a", "#1d7a66", "#e0a526", "#eef5f2", "#1f2d2a",
                        "Segoe UI", "Segoe UI Semibold", _minimal_decor),
    "Класна дошка": Theme("Класна дошка", "#24453a", "#f6f1d8", "#e8efe9", "#f2c14e", "#9fd3c7", "#2f5a4b", "#f6f1d8",
                          "Segoe Print", "Segoe Print", _board_decor),
}
DEFAULT_THEME = "Мінімал ГС"


def _paint(e: Element, t: Theme) -> None:
    if e.role == "title":
        e.color, e.font = t.title, t.title_font
    elif e.role == "body":
        e.color, e.font = t.body, t.font
    elif e.role in ("accent", "accent2"):
        e.fill = t.accent if e.role == "accent" else t.accent2
        e.line, e.color, e.font = e.fill, (t.bg if e.kind == "shape" else t.body), t.font
    elif e.role == "card":
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
        s.elements[:0] = t.decor(W, H, s.layout in ("Титул", "Тема уроку"))


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
    s.elements[:0] = t.decor(W, H, layout in ("Титул", "Тема уроку"))
    return s


def new_presentation(theme: str = DEFAULT_THEME, ratio: str = "16:9") -> Presentation:
    p = Presentation(ratio=ratio, theme=theme, font=THEMES[theme].font)
    p.slides.append(make_slide("Титул", p))
    return p
