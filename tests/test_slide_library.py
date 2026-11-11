"""InterSlide етап 3: бібліотека ≥150 об'єктів у ≥10 темах, пошук, вставка, перефарбування темою, PPTX з картинкою."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from pptx import Presentation as PP  # noqa: E402

from shkola_office.slide import library  # noqa: E402
from shkola_office.slide.model import Presentation  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow  # noqa: E402

D = Path(os.environ.get("ISLIDE_OUT") or tempfile.mkdtemp())
assert len(library.items()) >= 150 and len(library.topics()) >= 10
for it in library.items():
    assert (library.LIB_DIR / it["file"]).is_file(), it
    assert "#010101" in library.svg_text(it) or "#020202" in library.svg_text(it), it["id"]
assert [i["id"] for i in library.search("атом")] == ["atom"]
assert len(library.search("квіз")) >= 5 and all(i["topic"] == "Хімія" for i in library.search("", "Хімія"))

w = SlideWindow()
w.resize(1400, 820)
w.show()
w.lib_find.setText("колба")
assert w.lib_list.count() == 1
w.add_lib(w.lib_list.item(0).data(256))
e = w.slide().elements[-1]
assert e.kind == "image" and e.role == "lib:flask" and b"#135548" in w.pres.media[e.media]
w.set_theme("Класна дошка")
e = [x for x in w.slide().elements if x.role == "lib:flask"][0]
assert b"#f2c14e" in w.pres.media[e.media], "перефарбовано темою"
assert w.save_to(D / "lib.pptx")
pics = [s for s in PP(str(D / "lib.pptx")).slides[0].shapes if s.shape_type == 13]
assert pics, "SVG → PNG у PPTX"
assert w.save_to(D / "lib.islide") and Presentation.load(D / "lib.islide").slides[0].elements[-1].role == "lib:flask"
w.lib_find.setText("")
app.processEvents()
w.grab().save(str(D / "lib_window.png"))
print("БІБЛІОТЕКА OK", len(library.items()), D)
