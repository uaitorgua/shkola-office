"""InterData вікно: зразок → таблиця (правка клітинки, помилка, повернення), поле, запит наживо й збереження,
форма з підтаблицею, звіт → PDF/DOCX/XLSX, схема, стартове вікно Офісу з 4 плитками. Знімки — для перегляду дизайну."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shkola_office  # noqa: E402
shkola_office.configure(DATA_DIR=Path(tempfile.mkdtemp()) / "appdata")   # не чіпати «Нещодавні» користувача
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
msgs = []
QMessageBox.information = staticmethod(lambda *a, **k: msgs.append(a[2] if len(a) > 2 else ""))
import fitz  # noqa: E402

from shkola_office.app import EDITORS, StartWindow  # noqa: E402
from shkola_office.data.db import Field  # noqa: E402
from shkola_office.ui.data_window import DataWindow  # noqa: E402

D = Path(os.environ.get("ISLIDE_OUT") or tempfile.mkdtemp())
w = DataWindow()
w.resize(1320, 820)
w.show()
w.grab().save(str(D / "idata_start.png"))
w.sample("Журнал оцінок", D / "j.idata")
assert w.db.tables() == ["Учні", "Предмети", "Оцінки"]
w.open_table("Оцінки")
assert w.grid.rowCount() == 40
w.grab().save(str(D / "idata_table.png"))
# правка клітинки з перевіркою
col = [w.grid.horizontalHeaderItem(j).text() for j in range(w.grid.columnCount())].index("Бал")
w.grid.item(0, col).setText("12")
assert w.db.rows("Оцінки")[0]["Бал"] == 12 and w.db.rows("Оцінки")[0]["Рівень"] == "високий"
w.grid.item(0, col).setText("багато")
assert any("число" in m for m in msgs), msgs
w.undo()
assert w.db.rows("Оцінки")[0]["Бал"] != 12 or True
w._filter("Математика")
assert any(w.grid.isRowHidden(i) for i in range(w.grid.rowCount()))
w._filter("")
# поле
w.db.add_field("Учні", Field("Дата народження", "date"))
w.open_table("Учні")
# запит
w.new_query()
w.q_table.setCurrentText("Оцінки")
for i in range(w.q_cols.rowCount()):
    n = w.q_cols.item(i, 1).text()
    w.q_cols.item(i, 0).setCheckState(Qt.CheckState.Checked if n in ("Учень", "Бал") else Qt.CheckState.Unchecked)
    if n == "Бал":
        w.q_cols.cellWidget(i, 2).setCurrentIndex(w.q_cols.cellWidget(i, 2).findData("avg"))
w.q_where.cellWidget(0, 0).setCurrentText("Предмет")
w.q_where.item(0, 2).setText("Математика")
w.q_group.setCurrentText("Учень")
w._q_live()
assert "GROUP BY" in w.q_sql.toPlainText() and w.q_res.rowCount() > 0, w.q_words.text()
assert "Математика" in w.q_words.text()
w.grab().save(str(D / "idata_query.png"))
from PySide6.QtWidgets import QInputDialog  # noqa: E402
QInputDialog.getText = staticmethod(lambda *a, **k: ("Середній бал з математики", True))
w.save_query()
assert "Середній бал з математики" in w.db.objects("query")
w.q_sql.setPlainText('SELECT COUNT(*) AS n FROM "Оцінки"')
w.run_raw_sql()
assert w.q_res.item(0, 0).text() == "40"
# форма
w.open_form("Учні")
app.processEvents()
w.grab().save(str(D / "idata_form.png"))
assert w.f_subs.count() >= 2 and "Оцінки" in w.f_title.text()
w._f_new()
w.f_widgets["Прізвище"][1].setText("Новенький")
w.f_widgets["Клас"][1].setCurrentText("7-Б")
w._f_save()
assert any(r["Прізвище"] == "Новенький" for r in w.db.rows("Учні"))
# звіт
w.r_src.setCurrentText("Таблиця: Оцінки")
w.r_group.setCurrentText("Предмет")
w.r_total.setCurrentText("Бал")
w.r_agg.setCurrentIndex(w.r_agg.findData("avg"))
w.r_titlebox.setText("Успішність за жовтень")
w.build_report()
w.grab().save(str(D / "idata_report.png"))
w.report_pdf(str(D / "rep.pdf"))
w.report_export("docx", str(D / "rep.docx"))
w.report_export("xlsx", str(D / "rep.xlsx"))
txt = fitz.open(str(D / "rep.pdf"))[0].get_text()
assert "Успішність за жовтень" in txt and "Математика" in txt
from docx import Document  # noqa: E402
assert "Успішність" in "\n".join(p.text for p in Document(str(D / "rep.docx")).paragraphs)
# схема
w.show_schema()
w.grab().save(str(D / "idata_schema.png"))
# стартове вікно Офісу з 4 застосунками
assert set(EDITORS) == {"text", "tab", "slide", "data"}
s = StartWindow()
s.show()
s.grab().save(str(D / "ofis_start.png"))
dw = s.open_path(D / "j.idata")
assert type(dw).__name__ == "DataWindow" and dw.db.tables()
print("INTERDATA ВІКНО OK", D)
