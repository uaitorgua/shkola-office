"""InterSlide етап 2: 12 макетів у двох темах, перемикання теми зберігає ручні елементи, 4:3, PPTX."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from pptx import Presentation as PP  # noqa: E402

from shkola_office.slide.model import Element  # noqa: E402
from shkola_office.slide.themes import LAYOUTS, THEMES  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow, slide_image  # noqa: E402

D = Path(os.environ.get("ISLIDE_OUT") or tempfile.mkdtemp())
assert len(LAYOUTS) == 12 and len(THEMES) >= 2
w = SlideWindow()
for name in LAYOUTS[1:]:
    w.add_layout(name)
assert len(w.pres.slides) == 12
w.add_elem(Element("text", 300, 300, 200, 40, "моє", 20, "#ff0000"))
for theme in THEMES:
    w.set_theme(theme)
    t = THEMES[theme]
    assert all(s.bg == t.bg for s in w.pres.slides)
    assert any(e.text == "моє" and e.color == "#ff0000" for e in w.pres.slides[-1].elements), "ручний елемент"
    sheet = QImage(4 * 320, 3 * 180, QImage.Format.Format_RGB32)
    p = QPainter(sheet)
    for i, s in enumerate(w.pres.slides):
        p.drawImage((i % 4) * 320, (i // 4) * 180, slide_image(w.pres, s, 320))
    p.end()
    sheet.save(str(D / f"layouts_{theme}.png"))
    decor = sum(e.role == "decor" for e in w.pres.slides[0].elements)
    assert decor >= 1, theme
w.set_ratio("4:3")
assert all(e.x + e.w <= 721 for s in w.pres.slides for e in s.elements if e.role == "decor")
assert w.save_to(D / "t.pptx") and len(PP(str(D / "t.pptx")).slides) == 12
assert w.save_to(D / "t.islide")
w.load(D / "t.islide")
assert w.pres.theme == list(THEMES)[-1]
print("ТЕМИ Й МАКЕТИ OK", D)
