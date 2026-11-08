"""Етап 5: DOCX і XLSX з InterText/InterTab відкриваються в LibreOffice (headless → PDF) без втрат:
текст, таблиця, колонтитул із номером сторінки, формули XLSX перераховані. Без LibreOffice — пропуск."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOFFICE = shutil.which("soffice") or next((p for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                                                       "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                                                       "/usr/bin/soffice") if Path(p).exists()), None)
if not SOFFICE:
    print("LibreOffice не знайдено — пропуск")
    sys.exit(0)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
import fitz  # noqa: E402

import shkola_office.ui.editor_window as ew  # noqa: E402
from shkola_office.ui.doc_pages import HeaderFooter  # noqa: E402
from shkola_office.ui.sheet_extra import CondRule  # noqa: E402
from shkola_office.ui.sheet_window import SheetWindow  # noqa: E402

ew.adaptation_notice = lambda *a, **k: None
D = Path(tempfile.mkdtemp())


def to_pdf(src: Path) -> str:
    prof = D / "lo_profile"
    subprocess.run([SOFFICE, f"-env:UserInstallation=file:///{prof.as_posix()}", "--headless", "--convert-to", "pdf",
                    "--outdir", str(D / "pdf"), str(src)], check=True, timeout=180, capture_output=True)
    pdf = D / "pdf" / (src.stem + ".pdf")
    doc = fitz.open(str(pdf))
    return "\n".join(p.get_text() for p in doc), len(doc)


# ---- InterText → DOCX → LibreOffice ----
w = ew.EditorWindow()
w.set_html("<h1>Наказ про проведення олімпіади</h1>" + "<p>Відповідно до плану роботи закладу освіти.</p>" * 60
           + "<table border=1><tr><td>Клас</td><td>Учасники</td></tr><tr><td>7-А</td><td>12</td></tr></table>")
w.hf = HeaderFooter(footer="Сторінка {стор} з {усього}", skip_first=False)
assert w.save_to(D / "doc.docx")
text, pages = to_pdf(D / "doc.docx")
assert "Наказ про проведення олімпіади" in text and "7-А" in text, "текст і таблиця DOCX"
assert pages >= 2 and f"Сторінка 2 з {pages}" in text, ("колонтитул DOCX", pages)
print("DOCX у LibreOffice: OK, сторінок", pages)

# ---- InterTab → XLSX → LibreOffice ----
sw = SheetWindow()
s = sw.sheet()
for r, row in enumerate([["Учень", "Бал"], ["Іваненко", "10"], ["Петренко", "3"], ["Разом", "=SUM(B2:B3)"],
                         ["Середнє", "=ROUND(AVERAGE(B2:B3);1)"], ["Відмінники", '=COUNTIF(B2:B3;">=10")']]):
    for c, v in enumerate(row):
        s.set_cell(r, c, v)
s.cond.append(CondRule(1, 1, 2, 1, "між", "1", "3", "#fde2e1"))
sw._freeze()
assert sw.save_to(D / "tab.xlsx")
text, _ = to_pdf(D / "tab.xlsx")
for want in ("Іваненко", "13", "6,5", "6.5"):
    if want in ("6,5", "6.5"):
        continue
    assert want in text, ("XLSX", want, text[:300])
assert "6,5" in text or "6.5" in text, "AVERAGE у LibreOffice"
print("XLSX у LibreOffice: OK")
print("ЕТАП 5 LibreOffice OK")
