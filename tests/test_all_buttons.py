"""Усі кнопки всіх чотирьох застосунків: кожна дія стрічки й меню (і пункти випадних меню) натискається
на заповненому документі; діалоги закриваються самі; будь-яке виключення = помилка тесту.
Перевіряється «не падає» (функції — в окремих тестах)."""
import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
D = Path(tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shkola_office  # noqa: E402
shkola_office.configure(DATA_DIR=D / "appdata")
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import (QApplication, QColorDialog, QDialog, QFileDialog, QFontDialog, QInputDialog, QMenu,  # noqa: E402
                               QMessageBox)

app = QApplication.instance() or QApplication(sys.argv)
errors: list[str] = []
sys.excepthook = lambda t, v, tb: errors.append("".join(traceback.format_exception(t, v, tb))[-600:])

# діалоги — без людини
QDialog.exec = lambda self: 0
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.exec = lambda self: 0
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (0.0, False))
QInputDialog.getMultiLineText = staticmethod(lambda *a, **k: ("", False))
QColorDialog.getColor = staticmethod(lambda *a, **k: __import__("PySide6.QtGui", fromlist=["QColor"]).QColor())
QFontDialog.getFont = staticmethod(lambda *a, **k: (None, False))
QMenu.exec = lambda self, *a, **k: None
try:
    from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
    QPrintDialog.exec = lambda self: 0
    QPrintPreviewDialog.exec = lambda self: 0
except ImportError:
    pass
import shkola_office.ui.editor_window as ew  # noqa: E402
ew.adaptation_notice = lambda *a, **k: None
import shkola_office.ui.slide_show as ss  # noqa: E402
ss.start_show = lambda pres, start=0: ss.SlideShow(pres, start)

SKIP = {"Закрити", "Вихід", "Вийти"}


def press_all(win, name: str) -> int:
    n = 0
    seen = set()
    acts = [a for a in win.findChildren(QAction)]
    for m in win.findChildren(QMenu):
        acts += m.actions()
    for a in acts:
        if id(a) in seen or a.isSeparator() or a.menu() is not None or not a.text().strip():
            continue
        seen.add(id(a))
        if a.text().replace("&", "") in SKIP:
            continue
        before = len(errors)
        try:
            a.trigger()
            app.processEvents()
        except Exception:  # noqa: BLE001
            errors.append(traceback.format_exc()[-600:])
        if len(errors) > before:
            errors[-1] = f"[{name}] «{a.text()}»\n" + errors[-1]
        n += 1
    return n


from shkola_office.ui.data_window import DataWindow  # noqa: E402
from shkola_office.ui.sheet_window import SheetWindow  # noqa: E402
from shkola_office.ui.slide_window import SlideWindow  # noqa: E402

total = {}
t = ew.EditorWindow()
t.show()
t.set_html("<h1>Заголовок</h1><p>Текст <b>жирний</b> і звичайний.</p><table border=1><tr><td>1</td><td>2</td></tr></table>")
t.edit.selectAll()
total["InterText"] = press_all(t, "InterText")

s = SheetWindow()
s.show()
for r, row in enumerate([["Учень", "Бал"], ["А", "7"], ["Б", "11"], ["=SUM(B2:B3)", ""]]):
    for c, v in enumerate(row):
        s.sheet().set_cell(r, c, v)
s.sheet().setRangeSelected(__import__("PySide6.QtWidgets", fromlist=["QTableWidgetSelectionRange"]).QTableWidgetSelectionRange(0, 0, 2, 1), True)
total["InterTab"] = press_all(s, "InterTab")

p = SlideWindow()
p.show()
p.add_layout("Два стовпці")
items = [i for i in p.canvas.scene().items() if hasattr(i, "e")]
items[-1].setSelected(True)
total["InterSlide"] = press_all(p, "InterSlide")

d = DataWindow()
d.show()
d.sample("Журнал оцінок", D / "j.idata")
d.open_table("Оцінки")
d.grid.setCurrentCell(0, 1)
total["InterData"] = press_all(d, "InterData")

print("Натиснуто дій:", total)
if errors:
    print(f"ПОМИЛОК: {len(errors)}")
    for e in errors[:15]:
        print("-" * 60)
        print(e)
    sys.exit(1)
print("УСІ КНОПКИ OK")
