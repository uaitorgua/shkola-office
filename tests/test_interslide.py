"""InterSlide етап 1: слайди, елементи, .islide туди-назад, PPTX (python-pptx читає), PDF (fitz читає)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
import fitz  # noqa: E402
from pptx import Presentation as PP  # noqa: E402

from shkola_office.slide.model import Element, Presentation, content_slide  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow  # noqa: E402

D = Path(tempfile.mkdtemp())
w = SlideWindow()
w.show()
w.add_slide(content_slide("Дроби", "• Чисельник\n• Знаменник"))
w.add_elem(Element("shape", 600, 300, 200, 120, "½", 40, "#ffffff", shape="Еліпс", fill="#1d7a66", align="center"))
logo = Path(__file__).resolve().parents[1] / "shkola_office/assets/icons/book.svg"
png = D / "pic.png"
from PySide6.QtGui import QImage  # noqa: E402
QImage(40, 30, QImage.Format.Format_RGB32).save(str(png))
w.add_image(str(png))
w.slide().notes = "Запитати: що більше, ½ чи ⅓?"
w.dup_slide()
w.move_slide(-1)
assert len(w.pres.slides) == 3 and w.cur == 1
w.selected()[0:0]
it = [i for i in w.canvas.scene().items() if hasattr(i, "e") and i.e.kind == "shape"][0]
it.setSelected(True)
w._fmt(bold=None, size=+4)
assert it.e.bold and it.e.size == 44

assert w.save_to(D / "p.islide")
p2 = Presentation.load(D / "p.islide")
assert len(p2.slides) == 3 and p2.slides[1].notes.startswith("Запитати") and len(p2.media) == 1
assert p2.to_json() == w.pres.to_json()

assert w.save_to(D / "p.pptx")
pp = PP(str(D / "p.pptx"))
txt = " ".join(sh.text_frame.text for s in pp.slides for sh in s.shapes if sh.has_text_frame)
assert "Дроби" in txt and "½" in txt and len(pp.slides) == 3
assert pp.slides[1].notes_slide.notes_text_frame.text.startswith("Запитати")
assert any(sh.shape_type == 13 for sh in pp.slides[1].shapes)       # PICTURE

assert w.save_to(D / "p.pdf")
doc = fitz.open(str(D / "p.pdf"))
assert len(doc) == 3 and "Дроби" in doc[1].get_text() and abs(doc[0].rect.width / doc[0].rect.height - 16 / 9) < 0.01

w.set_ratio("4:3")
assert w.pres.size == (720, 540)
w.grab().save(str(D / "win.png"))
print("INTERSLIDE OK", D)
