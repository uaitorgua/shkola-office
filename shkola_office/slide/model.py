"""InterSlide: модель презентації без Qt. Одиниця — точка (pt): слайд 16:9 = 960×540, 4:3 = 720×540.
Формат .islide = zip: presentation.json + media/<файли>. Експорт PPTX — export_pptx()."""
from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

SIZES = {"16:9": (960, 540), "4:3": (720, 540)}
FORMAT_VERSION = 1


@dataclass
class Element:
    kind: str = "text"                 # text | shape | image
    x: float = 60
    y: float = 60
    w: float = 400
    h: float = 80
    text: str = ""
    size: float = 24                   # кегль, pt
    color: str = "#1f2d2a"
    bold: bool = False
    italic: bool = False
    align: str = "left"                # left | center | right
    fill: str = ""                     # заливка фігури/тла тексту ("" — без)
    line: str = ""
    shape: str = "Прямокутник"         # назва з ui.shapes.SHAPES
    media: str = ""                    # ім'я файлу в media/ для image
    font: str = ""                     # "" — шрифт теми
    role: str = ""                     # title | body | accent | decor — тема перефарбовує за роллю

    @classmethod
    def from_dict(cls, d: dict) -> "Element":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Slide:
    elements: list[Element] = field(default_factory=list)
    bg: str = "#ffffff"
    notes: str = ""
    layout: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Slide":
        return cls([Element.from_dict(e) for e in d.get("elements", [])], d.get("bg", "#ffffff"),
                   d.get("notes", ""), d.get("layout", ""))


@dataclass
class Presentation:
    slides: list[Slide] = field(default_factory=list)
    ratio: str = "16:9"
    title: str = ""
    font: str = "Segoe UI"
    theme: str = ""
    media: dict[str, bytes] = field(default_factory=dict, repr=False)

    @property
    def size(self) -> tuple[int, int]:
        return SIZES.get(self.ratio, SIZES["16:9"])

    def add_media(self, name: str, data: bytes) -> str:
        stem, suf = Path(name).stem or "img", Path(name).suffix.lower() or ".png"
        n, i = f"{stem}{suf}", 1
        while n in self.media and self.media[n] != data:
            n, i = f"{stem}_{i}{suf}", i + 1
        self.media[n] = data
        return n

    # ---------- .islide ----------
    def to_json(self) -> dict:
        return {"format": "islide", "version": FORMAT_VERSION, "ratio": self.ratio, "title": self.title,
                "font": self.font, "theme": self.theme, "slides": [{"bg": s.bg, "notes": s.notes, "layout": s.layout,
                                               "elements": [asdict(e) for e in s.elements]} for s in self.slides]}

    def save(self, path: Path) -> None:
        path = Path(path)
        used = {e.media for s in self.slides for e in s.elements if e.media}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("presentation.json", json.dumps(self.to_json(), ensure_ascii=False, indent=1))
            for n in used:
                if n in self.media:
                    z.writestr("media/" + n, self.media[n])

    @classmethod
    def load(cls, path: Path) -> "Presentation":
        with zipfile.ZipFile(path) as z:
            d = json.loads(z.read("presentation.json").decode("utf-8"))
            media = {n[6:]: z.read(n) for n in z.namelist() if n.startswith("media/") and len(n) > 6}
        return cls([Slide.from_dict(s) for s in d.get("slides", [])], d.get("ratio", "16:9"),
                   d.get("title", ""), d.get("font", "Segoe UI"), d.get("theme", ""), media)


def title_slide(title: str = "Тема уроку", sub: str = "Клас · дата", ratio: str = "16:9") -> Slide:
    W, H = SIZES[ratio]
    return Slide([Element("text", 60, H * 0.32, W - 120, 90, title, 44, "#135548", True, align="center"),
                  Element("text", 60, H * 0.32 + 100, W - 120, 50, sub, 22, "#5b6b67", align="center")],
                 layout="Титул")


def content_slide(title: str = "Заголовок", body: str = "• Перший пункт\n• Другий пункт", ratio: str = "16:9") -> Slide:
    W, H = SIZES[ratio]
    return Slide([Element("text", 50, 30, W - 100, 70, title, 34, "#135548", True),
                  Element("text", 50, 115, W - 100, H - 160, body, 22)], layout="Заголовок і текст")


# ---------- PPTX ----------
_PPTX_SHAPES = {"Прямокутник": "RECTANGLE", "Скруглений прямокутник": "ROUNDED_RECTANGLE", "Еліпс": "OVAL",
                "Трикутник": "ISOSCELES_TRIANGLE", "Ромб": "DIAMOND", "Стрілка →": "RIGHT_ARROW",
                "Зірка": "STAR_5_POINT", "Виноска": "RECTANGULAR_CALLOUT"}


def _rgb(c: str):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(c.lstrip("#")[:6].upper())


def export_pptx(pres: Presentation, path: Path, raster=None) -> None:
    """Редагований PPTX: текст лишається текстом, фігури — автофігурами, нотатки — нотатками доповідача."""
    import io

    from pptx import Presentation as PP
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt

    W, H = pres.size
    pp = PP()
    pp.slide_width, pp.slide_height = Pt(W), Pt(H)
    blank = pp.slide_layouts[6]
    al = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    for s in pres.slides:
        sl = pp.slides.add_slide(blank)
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = _rgb(s.bg or "#ffffff")
        for e in s.elements:
            box = (Pt(e.x), Pt(e.y), Pt(e.w), Pt(e.h))
            if e.kind == "image" and e.media in pres.media:
                data = pres.media[e.media]
                if e.media.lower().endswith(".svg"):          # PPTX не бере SVG напряму → PNG (raster від Qt)
                    if raster is None:
                        continue
                    data = raster(data, int(e.w * 4), int(e.h * 4))
                sl.shapes.add_picture(io.BytesIO(data), *box)
                continue
            if e.kind == "shape" and e.shape == "Лінія":
                ln = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Pt(e.x), Pt(e.y + e.h / 2), Pt(e.x + e.w), Pt(e.y + e.h / 2))
                ln.line.color.rgb = _rgb(e.line or e.fill or "#135548")
                continue
            if e.kind == "shape":
                sh = sl.shapes.add_shape(getattr(MSO_SHAPE, _PPTX_SHAPES.get(e.shape, "RECTANGLE")), *box)
                sh.fill.solid()
                sh.fill.fore_color.rgb = _rgb(e.fill or "#1d7a66")
                sh.line.color.rgb = _rgb(e.line or e.fill or "#135548")
            else:
                sh = sl.shapes.add_textbox(*box)
                if e.fill:
                    sh.fill.solid()
                    sh.fill.fore_color.rgb = _rgb(e.fill)
            tf = sh.text_frame
            tf.word_wrap = True
            for i, line in enumerate((e.text or "").split("\n")):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.alignment = al.get(e.align, PP_ALIGN.LEFT)
                r = p.add_run()
                r.text = line
                f = r.font
                f.size, f.bold, f.italic = Pt(e.size), e.bold, e.italic
                f.name = e.font or pres.font
                f.color.rgb = _rgb(e.color or "#000000")
        if s.notes:
            sl.notes_slide.notes_text_frame.text = s.notes
    pp.save(str(path))
