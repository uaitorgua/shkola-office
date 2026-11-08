"""Повний функціональний тест InterText та InterTab: кожна дія стрічки й меню викликається програмно
(діалоги підмінені типовими відповідями), перевіряються результати та відсутність винятків.
Запуск: python tests\\test_editors.py"""
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextCursor  # noqa: E402
from PySide6.QtWidgets import (QApplication, QColorDialog, QDialog, QFileDialog, QInputDialog, QMessageBox,  # noqa: E402
                               QTableWidgetSelectionRange, QToolButton)

app = QApplication.instance() or QApplication(sys.argv)
from shkola_office.ui.theme import STYLE  # noqa: E402
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
from shkola_office.ui.editor_window import EditorWindow  # noqa: E402
from shkola_office.ui.sheet_window import SheetWindow  # noqa: E402

D = Path(tempfile.mkdtemp())
errors: list[str] = []

# --- підміна діалогів: приймаємо типові значення ---
QDialog.exec = lambda self: 1
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: errors.append(f"critical: {a[2]}"))
QColorDialog.getColor = staticmethod(lambda *a, **k: QColor("#c0392b"))
QInputDialog.getText = staticmethod(lambda *a, **k: ("Тест", True))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (2.0, True))
_img = D / "img.png"
QImage(200, 100, QImage.Format.Format_RGB32).save(str(_img))
_n = [0]


def _save_name(*a, **k):
    _n[0] += 1
    flt = (a[3] if len(a) > 3 else k.get("filter", "")) or ""
    ext = "docx" if "docx" in flt else "pdf" if "pdf" in flt else "html" if "html" in flt else "txt" if "txt" in flt \
        else "xlsx" if "xlsx" in flt else "csv" if "csv" in flt else "bin"
    return str(D / f"f{_n[0]}.{ext}"), flt


QFileDialog.getSaveFileName = staticmethod(_save_name)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(_img) if "Зображення" in (a[1] if len(a) > 1 else "") else "", ""))


def run(label, fn):
    try:
        fn()
        app.processEvents()
    except Exception as e:
        errors.append(f"{label}: {type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")


def all_actions(win):
    seen, out = set(), []
    for b in win.findChildren(QToolButton):
        a = b.defaultAction()
        if a is not None and id(a) not in seen:
            seen.add(id(a))
            out.append(a)
    from PySide6.QtWidgets import QMenu
    for m in win.findChildren(QMenu):
        for a in m.actions():
            if a.text() and id(a) not in seen and not a.isSeparator():
                seen.add(id(a))
                out.append(a)
    return out


# ================= InterText =================
ed = EditorWindow(None, "<h1>Заголовок</h1><p>Абзац для перевірки редактора InterText.</p><p>Другий абзац.</p>")
ed.resize(1400, 900)
ed.show()
app.processEvents()
SKIP_TEXT = {"Закрити", "Друк", "Друк…", "Перегляд", "Попередній перегляд…", "Новий", "Виділити все"}
from shkola_office.ui.doc_pages import TEMPLATES
SKIP_TEXT |= set(TEMPLATES)  # шаблони замінюють текст; перевіряє tests/test_doc_pages.py
acts = all_actions(ed)
print(f"InterText: дій {len(acts)}")
for a in acts:
    if a.text() in SKIP_TEXT:
        continue
    ed.edit.setTextCursor(ed.edit.textCursor())
    ed.edit.moveCursor(QTextCursor.MoveOperation.End)
    run(f"InterText «{a.text()}»", a.trigger)
    if a.isCheckable():
        run(f"InterText «{a.text()}» off", a.trigger)
# сценарії з перевіркою результату
ed.edit.moveCursor(QTextCursor.MoveOperation.End)
ed.insert_table(2, 2, [["а", "б"], ["в", "г"]], header=True)
run("table add row", ed._add_row)
t = ed.edit.textCursor().currentTable()
assert t is not None and t.rows() == 3, "рядок таблиці"
ed.edit.moveCursor(QTextCursor.MoveOperation.End)
ed.insert_formula(r"\frac{a}{b}")
assert "a/b" in ed.edit.toPlainText(), "формула"
ed.insert_image(QImage(str(_img)))
run("image props", ed._image_props)
from shkola_office.ui.shapes import draw_shape, SHAPES
for kind in SHAPES:
    im = draw_shape(kind, 200, 100, text="Текст")
    assert not im.isNull() and im.width() >= 200, kind
run("shape dialog", ed._insert_shape)
from shkola_office.ui.editor_page import DstuDialog
assert ed.apply_dstu(DstuDialog(ed)) > 0, "ДСТУ"
for ext in ("docx", "pdf", "html", "txt"):
    p = ed.save_to(D / f"doc.{ext}")
    assert p and p.stat().st_size > 100, ext
ed2 = EditorWindow()
ed2.load(D / "doc.docx")
assert "Абзац для перевірки" in ed2.edit.toPlainText(), "DOCX round trip"
ed2.load(D / "doc.html")
assert "InterText" in ed2.edit.toPlainText(), "HTML"
from shkola_office.ui.editor_styles import DocStyle
ed.cb_docstyle.setCurrentText("Звичайний")
assert ed._apply_style() > 0 and ed.edit.setup.left == 20.0, "стиль Звичайний"
pst = ed._save_style(D / "style.json")
assert pst and DocStyle.load(pst).name == "Тест", "збереження стилю"
assert ed._load_style(D / "style.json") > 0 and ed.cb_docstyle.currentText() == "Тест", "завантаження стилю"
ed.cb_zoom.setCurrentIndex(2)
assert ed.edit.width() > 900, "масштаб"
ed.cb_zoom.setCurrentIndex(1)
ed.ruler.indents_changed.emit(30.0, 20.0)
assert round(ed.edit.textCursor().blockFormat().textIndent()) == 30, "лінійка"
ed.edit.document().setModified(False)
ed.close()
ed2.close()
print("InterText OK")

# ================= InterTab =================
sh = SheetWindow(None, {"Дані": [["Назва", "Бал", "Вага"], ["А", "10", "2"], ["Б", "7", "1"], ["В", "12", "3"]]})
sh.resize(1400, 800)
sh.show()
app.processEvents()
s = sh.sheet()
s.setCurrentCell(1, 1)
acts = all_actions(sh)
print(f"InterTab: дій {len(acts)}")
SKIP_TAB = {"Закрити", "Друк", "Друк…", "Перегляд", "Попередній перегляд…", "Новий"}
for a in acts:
    if a.text() in SKIP_TAB:
        continue
    s = sh.sheet()
    s.setCurrentCell(1, 1)
    run(f"InterTab «{a.text()}»", a.trigger)
# сценарії
sh.load(D / "f1.xlsx") if (D / "f1.xlsx").exists() else None
sh._new()
s = sh.sheet()
rows = [["Назва", "Бал", "Вага"], ["А", "10", "2"], ["Б", "7", "1"], ["В", "12", "3"]]
for i, r in enumerate(rows):
    for j, v in enumerate(r):
        s.set_cell(i, j, v)
sh.set_cell(4, 1, "=SUM(B2:B4)")
assert s.value(4, 1) == 29, "SUM"
sh.set_cell(4, 2, "=SUMIF(B2:B4;\">8\";C2:C4)")
assert s.value(4, 2) == 5, "SUMIF"
sh.set_cell(5, 0, '=VLOOKUP("Б";A2:C4;2)')
assert s.value(5, 0) == 7, "VLOOKUP"
sh.set_cell(5, 1, "=IF(B5>20;\"багато\";\"мало\")")
assert s.value(5, 1) == "багато", "IF"
sh.set_cell(1, 3, "=B2*C2")
s.fill_series((1, 3, 1, 3), (3, 3))
assert s.raw[(3, 3)] == "=B4*C4" and s.value(3, 3) == 36, "протягування формули"
s.set_cell(6, 0, "1")
s.set_cell(7, 0, "2")
s.fill_series((6, 0, 7, 0), (10, 0))
assert s.raw[(10, 0)] == "5", "серія"
s.setCurrentCell(0, 0)
s.set_format(bold=True, bg="#ffeeaa", align="center", num=None)
s.setCurrentCell(1, 1)
s.set_format(num="0.00")
assert s.item(1, 1).text() == "10,00", "формат 0,00"
s.clearSelection()
s.setRangeSelected(QTableWidgetSelectionRange(12, 0, 13, 1), True)
s.merge_selected()
assert s.rowSpan(12, 0) == 2, "об'єднання"
s.clearSelection()
s.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 2), True)
s.copy_sel()
s.setCurrentCell(15, 0)
s.paste()
assert s.raw[(16, 1)] == "10", "копіювання/вставка"
sh.add_sheet("Сорт", [["Назва", "Бал"], ["А", "10"], ["Б", "7"], ["В", "12"]])
sh.sheet().sort_by_column(1, descending=True)
assert sh.sheet().data()[1][0] == "В", "сортування"
sh.tabs.setCurrentIndex(0)
s = sh.sheet()
assert s.find_next("Назва"), "пошук"
s.setCurrentCell(3, 24)
assert s.columnCount() > 26, "автододавання стовпців"
s.insert_col(1)
assert s.raw.get((0, 2)) == "Бал", "вставка стовпця зсуває"
s.delete_col(1)
s.insert_row(1)
s.delete_row(1)
assert s.raw.get((0, 1)) == "Бал"
p = sh.save_to(D / "t.xlsx")
assert p and p.stat().st_size > 1000, "XLSX"
sh2 = SheetWindow()
sh2.load(D / "t.xlsx")
assert sh2.sheet().fmt.get((0, 0), {}).get("bold") and sh2.sheet().raw.get((4, 1), "").startswith("=SUM"), "XLSX round trip"
from shkola_office.ui.charts import ChartSpec, extract, render
s = sh.sheet()
s.clearSelection()
s.setRangeSelected(QTableWidgetSelectionRange(0, 0, 3, 2), True)
for kind in ("Стовпчикова", "Горизонтальна", "Лінійна", "Кругова"):
    spec = ChartSpec(kind=kind, title="Тест", r0=0, c0=0, r1=3, c1=2)
    cats, series = extract(s, spec)
    assert cats and series and len(series[0][1]) == len(cats), kind
    assert not render(cats, series, kind, "Тест").isNull(), kind
spec = sh._insert_chart()
assert spec is not None and s.charts, "графік додано"
for w in getattr(sh, "_chart_windows", []):
    w.close()
p = sh.save_to(D / "chart.xlsx")
from openpyxl import load_workbook
assert len(load_workbook(str(D / "chart.xlsx")).active._charts) == 1, "діаграма у XLSX"
# відкриття «з Excel»: діаграма, об'єднання, ширина → внутрішні ресурси
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
wbx = Workbook(); wsx = wbx.active; wsx.title = "Excel"
for r in (["Клас", "Хлопці", "Дівчата"], ["7-А", 12, 14], ["7-Б", 10, 15], ["8-А", 13, 11]):
    wsx.append(r)
chx = BarChart(); chx.title = "Учні"; chx.add_data(Reference(wsx, min_col=2, max_col=3, min_row=1, max_row=4), titles_from_data=True)
chx.set_categories(Reference(wsx, min_col=1, min_row=2, max_row=4)); wsx.add_chart(chx, "E2")
wsx.merge_cells("A6:C6"); wsx["A6"] = "Разом"; wsx.column_dimensions["A"].width = 30
wbx.save(str(D / "excel.xlsx"))
sh3 = SheetWindow(); sh3.load(D / "excel.xlsx"); s3 = sh3.sheet()
assert len(s3.charts) == 1 and s3.charts[0].kind == "Стовпчикова" and s3.charts[0].title == "Учні", "діаграма з Excel"
assert (s3.charts[0].r0, s3.charts[0].c0, s3.charts[0].r1, s3.charts[0].c1) == (0, 0, 3, 2), s3.charts[0]
assert s3.columnSpan(5, 0) == 3, "об'єднання з Excel"
assert s3.columnWidth(0) > 150, "ширина з Excel"
assert sh3.save_to(D / "excel2.xlsx") and len(load_workbook(str(D / "excel2.xlsx")).active._charts) == 1, "діаграма збережена назад"
sh3.close()
assert sh.save_pdf(D / "t.pdf", landscape=True, all_sheets=True) and (D / "t.pdf").stat().st_size > 1000, "PDF"
sh.add_sheet("Другий", [["x"]])
assert sh.tabs.count() >= 2
sh.close()
sh2.close()
print("InterTab OK")

if errors:
    print("ПОМИЛКИ:\n" + "\n".join(errors))
    sys.exit(1)
print("УСІ ФУНКЦІЇ InterText/InterTab OK")
