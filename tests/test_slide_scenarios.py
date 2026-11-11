"""InterSlide етап 5: 7 тем, 6 сценаріїв, PPTX відкривається в LibreOffice (headless → PDF) з текстом і кількістю слайдів."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
import fitz  # noqa: E402

from shkola_office.slide.model import export_pptx, static_slides  # noqa: E402
from shkola_office.slide.scenarios import SCENARIOS, build  # noqa: E402
from shkola_office.slide.themes import THEMES  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow, slide_image, svg_png  # noqa: E402

D = Path(os.environ.get("ISLIDE_OUT") or tempfile.mkdtemp())
assert len(THEMES) >= 7 and len(SCENARIOS) == 6
for name in SCENARIOS:
    p = build(name)
    assert p.slides and p.theme == SCENARIOS[name][0], name
    texts = " ".join(e.text for s in p.slides for e in s.elements)
    assert "Тема уроку" in texts or name.split()[0] in texts or "Квіз" in texts, name
    sheet = QImage(4 * 320, ((len(p.slides) + 3) // 4) * 180, QImage.Format.Format_RGB32)
    pt = QPainter(sheet)
    for i, s in enumerate(p.slides):
        pt.drawImage((i % 4) * 320, (i // 4) * 180, slide_image(p, s, 320))
    pt.end()
    sheet.save(str(D / f"scenario_{name}.png"))

w = SlideWindow()
w.from_scenario("Батьківські збори")
assert w.pres.title == "Батьківські збори" and len(w.pres.slides) == 6

SOFFICE = shutil.which("soffice") or next((p for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                                                       "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                                                       "/usr/bin/soffice") if Path(p).exists()), None)
if SOFFICE:
    p = build("Урок-пояснення")
    src = D / "lo_lesson.pptx"
    export_pptx(p, src, raster=svg_png)
    prof = D / "lo_profile"
    subprocess.run([SOFFICE, f"-env:UserInstallation=file:///{prof.as_posix()}", "--headless", "--convert-to", "pdf",
                    "--outdir", str(D / "lo"), str(src)], check=True, timeout=240, capture_output=True)
    doc = fitz.open(str(D / "lo" / "lo_lesson.pdf"))
    txt = "\n".join(pg.get_text() for pg in doc)
    assert len(doc) == len(static_slides(p)), (len(doc), len(static_slides(p)))
    for want in ("Тема уроку", "Нове поняття", "Перевірка розуміння", "Домашнє завдання"):
        assert want in txt, want
    pix = doc[3].get_pixmap(dpi=60)
    pix.save(str(D / "lo_slide4.png"))
    print("LibreOffice: PPTX відкрито,", len(doc), "слайдів")
else:
    print("LibreOffice не знайдено — перевірку PPTX пропущено")
print("СЦЕНАРІЇ OK", D)
