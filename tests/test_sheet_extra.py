"""Етап 4 InterTab: нові функції й формати, фільтр, закріплення, умовне форматування, шаблони, XLSX."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from shkola_office.ui.sheet_extra import CondRule, TEMPLATES, clear_filter, filter_column  # noqa: E402
from shkola_office.ui.sheet_model import fmt_value  # noqa: E402
from shkola_office.ui.sheet_window import SheetWindow  # noqa: E402

w = SheetWindow()
w.resize(1200, 700)
w.show()
s = w.sheet()
data = [["Клас", "Бал"], ["5-А", "10"], ["5-Б", "3"], ["5-А", "7"], ["5-Б", "12"], ["5-А", "5"]]
for r, row in enumerate(data):
    for c, v in enumerate(row):
        s.set_cell(r, c, v)
F = {"=COUNTIFS(A2:A6;\"5-А\";B2:B6;\">5\")": 2, "=SUMIFS(B2:B6;A2:A6;\"5-Б\")": 15, "=AVERAGEIFS(B2:B6;A2:A6;\"5-А\")": 22 / 3,
     "=MEDIAN(B2:B6)": 7, "=RANK(B2;B2:B6)": 2, "=ROUNDUP(2.31;1)": 2.4, "=ROUNDDOWN(2.39;1)": 2.3, "=MAXIFS(B2:B6;A2:A6;\"5-А\")": 10,
     "=COUNTBLANK(C1:C3)": 3}
for i, (f, want) in enumerate(F.items()):
    s.set_cell(10 + i, 0, f)
    got = s.value(10 + i, 0)
    assert abs(float(got) - want) < 1e-9, (f, got)
assert fmt_value(1234.5, "грн") == "1 234,50 ₴" and fmt_value(46000, "дата") == "09.12.2025", fmt_value(46000, "дата")

assert filter_column(s, 0, {"5-А"}) >= 2 and s.isRowHidden(2) and s.isRowHidden(4) and not s.isRowHidden(1)
clear_filter(s)
assert not s.isRowHidden(2)

s.cond.append(CondRule(1, 1, 5, 1, "між", "1", "3", "#fde2e1"))
s.recalc()
assert s.item(2, 1).background().color().name() == "#fde2e1" and s.item(1, 1).background().color().name() != "#fde2e1"

w._freeze()
assert s.freeze == 1 and s._frozen.isVisible()

for name in TEMPLATES:
    t = w.add_template(name)
    assert t.freeze == 1 and t.raw, name
journal = w.add_template("Журнал оцінок")
journal.set_cell(1, 2, "11")
journal.set_cell(1, 3, "2")
assert journal.value(1, 12) == 6.5, journal.value(1, 12)
assert journal.item(1, 3).background().color().name() == "#fde2e1"

d = Path(tempfile.mkdtemp())
assert w.save_to(d / "t.xlsx")
from openpyxl import load_workbook  # noqa: E402
wb = load_workbook(d / "t.xlsx")
ws = wb[wb.sheetnames[0]]
assert ws.freeze_panes == "A2" and len(ws.conditional_formatting) >= 1
assert wb["Журнал оцінок"].freeze_panes == "A2" and len(wb["Журнал оцінок"].conditional_formatting) >= 1
import shkola_office.ui.editor_window as _sw  # noqa: E402
_sw.adaptation_notice = lambda *a, **k: None   # модальне попередження
w2 = SheetWindow()
w2.load(d / "t.xlsx")
app.processEvents()
assert w2.sheet().freeze == 1
print("ЕТАП 4 InterTab OK")
