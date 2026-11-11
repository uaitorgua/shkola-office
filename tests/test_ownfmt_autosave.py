"""Власні формати .itext/.itab (без втрат того, чого не тримає DOCX/XLSX) і автозбереження всіх редакторів:
типовий файл лишається у своєму форматі, резервна копія — у власному, відновлення після збою."""
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
D = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(D / "appdata")                    # не чіпати справжні дані користувача
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shkola_office  # noqa: E402
shkola_office.configure(DATA_DIR=D / "appdata" / "ofis-shkola")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
import shkola_office.ui.editor_window as ew  # noqa: E402
ew.adaptation_notice = lambda *a, **k: None
from shkola_office.app import StartWindow  # noqa: E402
from shkola_office.ui import autosave  # noqa: E402
from shkola_office.ui.doc_pages import HeaderFooter  # noqa: E402
from shkola_office.ui.sheet_extra import CondRule  # noqa: E402
from shkola_office.ui.sheet_window import SheetWindow  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow  # noqa: E402

# ---- .itext ----
t = ew.EditorWindow()
t.set_html("<h1>Наказ № 5</h1><p>Про <b>олімпіаду</b>.</p>")
t.hf = HeaderFooter(header="ліцей", footer="Сторінка {стор}", skip_first=False)
t.edit.setup.left = 25.0
assert t.save_to(D / "n.itext")
assert set(zipfile.ZipFile(D / "n.itext").namelist()) >= {"document.html", "meta.json"}
t2 = ew.EditorWindow()
t2.load(D / "n.itext")
assert "олімпіаду" in t2.edit.toPlainText() and t2.hf.footer == "Сторінка {стор}" and t2.edit.setup.left == 25.0

# ---- .itab ----
s = SheetWindow()
sh = s.sheet()
for r, row in enumerate([["Учень", "Бал"], ["А", "3"], ["Б", "11"], ["Разом", "=SUM(B2:B3)"]]):
    for c, v in enumerate(row):
        sh.set_cell(r, c, v)
sh.cond.append(CondRule(1, 1, 2, 1, "<", "4", color="#fde2e1"))
sh.fmt[(0, 0)] = {"bold": True}
sh.setSpan(5, 0, 1, 2)
s._freeze()
assert s.save_to(D / "t.itab")
s2 = SheetWindow()
s2.load(D / "t.itab")
app.processEvents()
x = s2.sheet()
assert x.raw[(3, 1)] == "=SUM(B2:B3)" and float(x.value(3, 1)) == 14
assert x.cond and x.cond[0].op == "<" and x.freeze == 1 and x.fmt[(0, 0)]["bold"] and x.columnSpan(5, 0) == 2
assert x.item(1, 1).background().color().name() == "#fde2e1"

# ---- автозбереження: типовий файл лишається типовим + копія у власному ----
s3 = SheetWindow()
s3.sheet().set_cell(0, 0, "x")
assert s3.save_to(D / "work.xlsx") and not s3.is_dirty()
s3.sheet().set_cell(0, 0, "змінено")
assert s3.is_dirty() and s3.autosave.tick()
from openpyxl import load_workbook  # noqa: E402
assert load_workbook(D / "work.xlsx").active["A1"].value == "змінено" and not s3.is_dirty()
assert s3.autosave.backup.suffix == ".itab" and s3.autosave.backup.exists()

d = ew.EditorWindow()
d.set_html("<p>новий, ще без файлу</p>")
d.edit.document().setModified(True)
assert d.autosave.tick() and d.path is None and d.autosave.backup.suffix == ".itext"

p = SlideWindow()
p.add_layout("Два стовпці")
assert p.is_dirty() and p.autosave.tick() and p.autosave.backup.suffix == ".islide"

# ---- «збій»: копії лишились → відновлення в стартовому вікні ----
items = autosave.pending()
assert {i["kind"] for i in items} >= {"tab", "text", "slide"}, items
st = StartWindow()
n = st.offer_restore(ask=lambda q: True)
assert n >= 3 and not autosave.pending()
restored = [w for w in st.windows if type(w).__name__ == "EditorWindow"]
assert restored and "новий, ще без файлу" in restored[0].edit.toPlainText() and restored[0].is_dirty()
rt = [w for w in st.windows if type(w).__name__ == "SheetWindow"][0]
assert rt.path == D / "work.xlsx", rt.path                    # «Зберегти» піде в той самий XLSX

# ---- нормальне закриття прибирає копію ----
s3.autosave.tick()
s3.mark_clean()
s3.close()
assert not s3.autosave.backup.exists()
print("ФОРМАТИ Й АВТОЗБЕРЕЖЕННЯ OK", D)
