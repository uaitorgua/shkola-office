"""InterData: вікно бази. Ліворуч навігатор із чотирма блоками (Таблиці · Запити · Форми · Звіти) і схемою зв'язків,
праворуч робоча область відповідного блоку. Кожна зміна одразу записується у файл .idata (SQLite)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..config import APP_NAME
from ..data.db import TYPES, Database, DataError, Field, HasDependents
from ..data.query import AGG, OPS, Query, auto_form, report, report_html, report_xlsx, run_sql, sub_rows
from ..data.samples import SAMPLES, build as build_sample
from . import icons
from .banner import Banner
from .logo import app_icon
from .ribbon import RIBBON_STYLE, Ribbon

INTERDATA = "InterData"
BLOCKS = ("Таблиці", "Запити", "Форми", "Звіти")


def fmt(v, ftype: str = "") -> str:
    if v is None:
        return ""
    if ftype == "bool":
        return "так" if v else "ні"
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-" and v[:4].isdigit():
        return f"{v[8:10]}.{v[5:7]}.{v[0:4]}"
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def fill_table(w: QTableWidget, cols: list[str], rows: list, types: dict | None = None) -> None:
    w.clear()
    w.setColumnCount(len(cols))
    w.setRowCount(len(rows))
    w.setHorizontalHeaderLabels(cols)
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            v = r[c] if isinstance(r, dict) else r[j]
            it = QTableWidgetItem(fmt(v, (types or {}).get(c, "")))
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            w.setItem(i, j, it)
    w.resizeColumnsToContents()
    w.horizontalHeader().setStretchLastSection(True)


class FieldDialog(QDialog):
    """Нове поле: назва, тип і його налаштування (список, таблиця для зв'язку, формула)."""

    def __init__(self, parent, db: Database, tbl: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Нове поле · {tbl}")
        self.name = QLineEdit()
        self.type = QComboBox()
        for k, v in TYPES.items():
            self.type.addItem(v, k)
        self.link = QComboBox()
        self.link.addItems([t for t in db.tables() if t != tbl])
        self.choices = QLineEdit()
        self.choices.setPlaceholderText("через кому: 5-А, 5-Б, 6-А")
        self.formula = QLineEdit()
        self.formula.setPlaceholderText("=[Бал1]+[Бал2]  або  ЯКЩО([Бал]>=10;\"так\";\"ні\")")
        self.req = QCheckBox("обов'язкове")
        self.uniq = QCheckBox("без повторів")
        lay = QFormLayout(self)
        lay.addRow("Назва:", self.name)
        lay.addRow("Тип:", self.type)
        lay.addRow("Таблиця для зв'язку:", self.link)
        lay.addRow("Варіанти списку:", self.choices)
        lay.addRow("Формула:", self.formula)
        lay.addRow(self.req, self.uniq)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)
        self.type.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self) -> None:
        t = self.type.currentData()
        self.link.setEnabled(t == "link")
        self.choices.setEnabled(t == "choice")
        self.formula.setEnabled(t == "formula")

    def field(self) -> Field:
        t = self.type.currentData()
        return Field(self.name.text().strip(), t, self.req.isChecked(), self.uniq.isChecked(),
                     [c.strip() for c in self.choices.text().split(",") if c.strip()] if t == "choice" else [],
                     self.link.currentText() if t == "link" else "", self.formula.text().strip() if t == "formula" else "")


class Schema(QGraphicsView):
    """Схема бази: таблиці-картки й лінії зв'язків (будується сама)."""

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHints(self.renderHints())
        self.setBackgroundBrush(QColor("#f4f8f6"))

    def draw(self, db: Database) -> None:
        sc = QGraphicsScene()
        boxes = {}
        for i, t in enumerate(db.tables()):
            fs = db.fields(t)
            x, y = (i % 3) * 270, (i // 3) * 260
            h = 34 + 20 * len(fs)
            sc.addRect(QRectF(x, y, 220, h), QPen(QColor("#135548"), 2), QBrush(QColor("#ffffff")))
            sc.addRect(QRectF(x, y, 220, 30), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#135548")))
            nm = next((r for r in db.relations() if r["kind"] == "N:M" and r["via"] == t), None)
            tt = sc.addText(t, QFont("Segoe UI", 11, QFont.Weight.Bold))
            if nm:
                note = sc.addText(f"проміжна: {nm['from']} ∞ — ∞ {nm['to']}", QFont("Segoe UI", 9))
                note.setDefaultTextColor(QColor("#8a5a00"))
                note.setPos(x, y + 34 + 20 * len(fs) + 2)
            tt.setDefaultTextColor(QColor("#ffffff"))
            tt.setPos(x + 6, y + 2)
            for j, f in enumerate(fs):
                mark = "🔗 " if f.type == "link" else ("ƒ " if f.type == "formula" else "")
                ft = sc.addText(f"{mark}{f.name} · {TYPES[f.type].lower()}", QFont("Segoe UI", 9))
                ft.setDefaultTextColor(QColor("#1f2d2a"))
                ft.setPos(x + 6, y + 32 + 20 * j)
            boxes[t] = (x, y, h, {f.name: j for j, f in enumerate(fs)})
        pen = QPen(QColor("#e0a526"), 2.5)
        for t in db.tables():
            for f in db.fields(t):
                if f.type == "link" and f.link in boxes:
                    x, y, h, idx = boxes[t]
                    bx, by, bh, _ = boxes[f.link]
                    fy = y + 44 + 20 * idx[f.name]
                    left = bx + 110 < x + 110                       # довідник ліворуч — лінія з лівого краю
                    a = QPointF(x if left else x + 220, fy)
                    b = QPointF(bx + 220 if left else bx, by + 15)
                    mid = (a.x() + b.x()) / 2 if abs(a.x() - b.x()) > 40 else a.x() + (-30 if left else 30)
                    from PySide6.QtGui import QPainterPath
                    path = QPainterPath(a)
                    path.lineTo(mid, a.y())
                    path.lineTo(mid, b.y())
                    path.lineTo(b)
                    lp = QPen(pen)
                    if not f.required:                               # необов'язковий зв'язок — пунктир
                        lp.setStyle(Qt.PenStyle.DashLine)
                    item = sc.addPath(path, lp)
                    item.setZValue(-1)                               # лінії під картками таблиць
                    lab = sc.addText("1 — 1" if f.unique else "1 — ∞", QFont("Segoe UI", 9, QFont.Weight.Bold))
                    lab.setDefaultTextColor(QColor("#8a5a00"))
                    lab.setPos(mid + 4, (a.y() + b.y()) / 2 - 10)
                    sc.addEllipse(b.x() - 4, b.y() - 4, 8, 8, pen, QBrush(QColor("#e0a526")))
        self.setScene(sc)


class DataWindow(QMainWindow):
    def __init__(self, parent=None, path: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{INTERDATA} · {APP_NAME}")
        self.setWindowIcon(app_icon())
        self.resize(1320, 820)
        self.setStyleSheet(RIBBON_STYLE + "QTreeWidget#idnav{font-size:13px;background:#f7faf9;border:none;"
                           "border-right:1px solid #dfe9e5;padding:6px 4px}"
                           "QTreeWidget#idnav::item{padding:2px 6px;border-radius:6px;color:#1f2d2a}"
                           "QTreeWidget#idnav::item:hover{background:#e8f3ef}"
                           "QTreeWidget#idnav::item:selected{background:#d5ece4;color:#0f3f35}"
                           " QTreeWidget{font-size:13px} QLabel#words{color:#135548;font-size:14px;"
                           "background:#eef7f3;border-radius:8px;padding:8px} QLabel#hint{color:#5b6b67}")
        self.db: Database | None = None
        self.path: Path | None = None
        self.nav = QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setMinimumWidth(250)
        self.nav.setIndentation(14)
        self.nav.setRootIsDecorated(False)
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setObjectName("idnav")
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav.itemClicked.connect(self._nav)
        self.stack = QStackedWidget()
        self.stack.currentChanged.connect(self._sync_ribbon)
        self.pages = {k: getattr(self, f"_page_{k}")() for k in ("start", "table", "query", "form", "report", "schema")}
        for w in self.pages.values():
            self.stack.addWidget(w)
        sp = QSplitter()
        sp.addWidget(self.nav)
        sp.addWidget(self.stack)
        sp.setStretchFactor(1, 1)
        self.setCentralWidget(sp)
        self._ribbon()
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        tl.addWidget(Banner(INTERDATA, "БАЗА ДАНИХ · ТАБЛИЦІ · ЗАПИТИ · ФОРМИ · ЗВІТИ", compact=True))
        tl.addWidget(self.ribbon)
        self.setMenuWidget(top)
        self.cur_table = ""
        if path:
            self.load(path)
        else:
            self.stack.setCurrentWidget(self.pages["start"])

    # ---------- стрічка ----------
    def _ribbon(self) -> None:
        rb = Ribbon(self)
        self.ribbon = rb
        mb = self.menuBar()
        f = mb.addMenu("Файл")
        f.addAction("Нова база…", self.new_db).setShortcut("Ctrl+N")
        f.addAction("Відкрити…", self.open_dialog).setShortcut("Ctrl+O")
        sm = f.addMenu("Зразкова база")
        for s in SAMPLES:
            sm.addAction(s, lambda s=s: self.sample(s))
        f.addSeparator()
        f.addAction("Імпорт CSV/XLSX…", self.import_dialog)
        f.addAction("Експорт у XLSX…", lambda: self.export("xlsx"))
        f.addAction("Експорт таблиці в CSV…", lambda: self.export("csv"))
        f.addAction("Експорт SQL…", lambda: self.export("sql"))
        t = rb.tab("Таблиці")
        g = t.group("Таблиця")
        g.big("Нова", "table", self.new_table)
        g.big("Імпорт", "file-import", self.import_dialog, tip="CSV або XLSX: типи полів визначаться самі")
        g = t.group("Записи")
        g.big("Додати", "plus", self.add_row, key="Ctrl+Shift+=")
        g.big("Видалити", "trash", self.del_row)
        g.big("Повернути", "undo", self.undo, key="Ctrl+Z", tip="Повернути як було останню зміну (разом із каскадом)")
        g = t.group("Поля")
        g.big("Нове поле", "layers", self.add_field)
        g.big("Зв'язок ∞—∞", "merge", self.add_nm, tip="Багато-до-багатьох через проміжну таблицю (напр. Учні ↔ Гуртки)")
        g.big("Змінити тип", "wand", self.change_type, tip="Змінити тип поля з перевіркою записів, що не підходять")
        g = t.group("Навчання")
        g.big("Нормалізація", "merge", self.normalize, tip="Знайти повтори й винести їх в окрему таблицю зі зв'язком")
        g = t.group("Пошук")
        self.find = QLineEdit()
        self.find.setPlaceholderText("Пошук у таблиці…")
        self.find.setFixedWidth(200)
        self.find.textChanged.connect(self._filter)
        g.widget(self.find)
        qt = rb.tab("Запити")
        g = qt.group("Запит")
        g.big("Новий", "search", self.new_query)
        g.big("Виконати", "eye", self.run_query, key="F5")
        g.big("Зберегти", "save", self.save_query)
        g = qt.group("Дія над записами")
        g.big("Оновити", "edit", lambda: self.action_query("update"),
              tip="Змінити значення поля в усіх записах, що відповідають умовам конструктора")
        g.big("Видалити", "trash", lambda: self.action_query("delete"),
              tip="Видалити всі записи, що відповідають умовам конструктора")
        g = qt.group("SQL")
        g.big("Виконати SQL", "formula", self.run_raw_sql, tip="Пісочниця: лише читання")
        ft = rb.tab("Форми")
        g = ft.group("Форма")
        g.big("Форма таблиці", "file-lines", lambda: self.open_form(self.cur_table or (self.db.tables()[0] if self.db and self.db.tables() else "")))
        rt = rb.tab("Звіти")
        g = rt.group("Звіт")
        g.big("Побудувати", "sheet", self.build_report)
        g.big("Зберегти", "save", self.save_report)
        g = rt.group("Вивести")
        g.big("Друк / PDF", "print", self.report_pdf)
        g.big("У DOCX", "file-word", lambda: self.report_export("docx"), tip="Відкриється в InterText і в інших редакторах документів")
        g.big("У XLSX", "file-excel", lambda: self.report_export("xlsx"), tip="Відкриється в InterTab і в інших табличних редакторах")
        nt = rb.tab("Навчання")
        g = nt.group("Завдання з перевіркою")
        g.big("Створити", "new", self.make_task, tip="Зберегти базу й поточний запит як еталон завдання (.itask)")
        g.big("Відкрити", "folder-open", self.load_task, tip="Відкрити завдання вчителя (.itask)")
        g.big("Перевірити", "check", self.check_task, key="F9", tip="Звірити ваш запит з еталоном")
        sc = rb.tab("Схема")
        g = sc.group("Зв'язки")
        g.big("Схема бази", "merge", self.show_schema)
        rb.finish(mb)

    def _sync_ribbon(self, _i: int) -> None:
        """Вкладка стрічки йде за блоком, з яким працюють."""
        if not hasattr(self, "ribbon"):
            return
        page = self.stack.currentWidget()
        names = {"table": "Таблиці", "query": "Запити", "form": "Форми", "report": "Звіти", "schema": "Схема"}
        key = next((k for k, w in self.pages.items() if w is page), "")
        for i in range(self.ribbon.count()):
            if self.ribbon.tabText(i) == names.get(key):
                self.ribbon.setCurrentIndex(i)

    # ---------- сторінки ----------
    def _page_start(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch(1)
        lab = QLabel("<h2 style='color:#135548'>InterData — база даних для школи</h2>"
                     "<p>Створіть нову базу, відкрийте файл (.idata, .db, .sqlite), імпортуйте CSV чи XLSX "
                     "або почніть зі зразка.</p>")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.addStretch(1)
        for t, s in (("Нова база", self.new_db), ("Відкрити…", self.open_dialog),
                     *[(f"Зразок: {x}", (lambda x=x: self.sample(x))) for x in SAMPLES]):
            b = QPushButton(t)
            b.setMinimumHeight(40)
            b.clicked.connect(s)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(2)
        return w

    def _page_table(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.t_title = QLabel()
        self.t_title.setObjectName("words")
        self.grid = QTableWidget()
        self.grid.setAlternatingRowColors(True)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.grid.itemChanged.connect(self._cell_edited)
        self.t_hint = QLabel()
        self.t_hint.setObjectName("hint")
        lay.addWidget(self.t_title)
        lay.addWidget(self.grid, 1)
        lay.addWidget(self.t_hint)
        return w

    def _page_query(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.q_table = QComboBox()
        self.q_table.setMinimumWidth(160)
        self.q_table.currentTextChanged.connect(self._q_fields)
        top.addWidget(QLabel("З таблиці:"))
        top.addWidget(self.q_table)
        self.q_group = QComboBox()
        self.q_group.setMinimumWidth(160)
        top.addWidget(QLabel("Для кожного:"))
        top.addWidget(self.q_group)
        self.q_order = QComboBox()
        self.q_order.setMinimumWidth(160)
        self.q_desc = QCheckBox("від більшого")
        top.addWidget(QLabel("Впорядкувати:"))
        top.addWidget(self.q_order)
        top.addWidget(self.q_desc)
        self.q_limit = QSpinBox(maximum=100000)
        self.q_limit.setSpecialValueText("усі")
        top.addWidget(QLabel("Показати:"))
        top.addWidget(self.q_limit)
        top.addStretch(1)
        lay.addLayout(top)
        mid = QHBoxLayout()
        self.q_cols = QTableWidget(0, 3)
        self.q_cols.setHorizontalHeaderLabels(["Показати", "Поле", "Підсумок"])
        self.q_cols.verticalHeader().hide()
        self.q_where = QTableWidget(3, 3)
        self.q_where.setHorizontalHeaderLabels(["Поле", "Умова", "Значення"])
        self.q_where.verticalHeader().hide()
        b = QVBoxLayout()
        b.addWidget(QLabel("Що показати"))
        b.addWidget(self.q_cols)
        mid.addLayout(b, 1)
        b = QVBoxLayout()
        b.addWidget(QLabel("Умови (усі разом)"))
        b.addWidget(self.q_where)
        mid.addLayout(b, 1)
        lay.addLayout(mid, 2)
        self.q_words = QLabel()
        self.q_words.setObjectName("words")
        self.q_words.setWordWrap(True)
        lay.addWidget(self.q_words)
        self.q_sql = QPlainTextEdit()
        self.q_sql.setMaximumHeight(110)
        self.q_sql.setFont(QFont("Consolas", 10))
        self._sql_edited = False
        self.q_sql.textChanged.connect(lambda: setattr(self, "_sql_edited", self.q_sql.hasFocus()))
        lay.addWidget(QLabel("SQL (оновлюється сам; можна змінити й натиснути «Виконати SQL»):"))
        lay.addWidget(self.q_sql)
        self.q_res = QTableWidget()
        lay.addWidget(self.q_res, 3)
        for s in (self.q_group.currentIndexChanged, self.q_order.currentIndexChanged, self.q_desc.toggled,
                  self.q_limit.valueChanged):
            s.connect(self._q_live)
        self.q_cols.itemChanged.connect(self._q_live)
        self.q_where.itemChanged.connect(self._q_live)
        self.q_name = ""
        return w

    def _page_form(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.f_title = QLabel()
        self.f_title.setObjectName("words")
        self.f_title.setSizePolicy(self.f_title.sizePolicy().horizontalPolicy(), self.f_title.sizePolicy().Policy.Maximum)
        lay.addWidget(self.f_title)
        nav = QHBoxLayout()
        for t, s in (("◀", lambda: self._f_go(-1)), ("▶", lambda: self._f_go(1)), ("Новий запис", self._f_new),
                     ("Зберегти", self._f_save), ("Видалити", self._f_delete)):
            b = QPushButton(t)
            b.clicked.connect(s)
            nav.addWidget(b)
        self.f_pos = QLabel()
        nav.addWidget(self.f_pos)
        nav.addStretch(1)
        lay.addLayout(nav)
        self.f_box = QWidget()
        self.f_layout = QFormLayout(self.f_box)
        lay.addWidget(self.f_box)
        self.f_subs = QVBoxLayout()
        lay.addLayout(self.f_subs, 1)
        self.f_ids: list[int] = []
        self.f_i = 0
        self.f_widgets: dict = {}
        return w

    def _page_report(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.r_src = QComboBox()
        self.r_src.currentTextChanged.connect(self._r_cols)
        self.r_group = QComboBox()
        self.r_total = QComboBox()
        self.r_agg = QComboBox()
        for k, v in AGG.items():
            if k:
                self.r_agg.addItem(v, k)
        self.r_titlebox = QLineEdit()
        self.r_titlebox.setPlaceholderText("Заголовок звіту")
        for cb in (self.r_src, self.r_group, self.r_total, self.r_agg):
            cb.setMinimumWidth(150)
        self.r_src.setMinimumWidth(220)
        for lab, wd in (("Джерело:", self.r_src), ("Групувати за:", self.r_group), ("Підсумок для:", self.r_total),
                        ("", self.r_agg), ("", self.r_titlebox)):
            if lab:
                top.addWidget(QLabel(lab))
            top.addWidget(wd)
        lay.addLayout(top)
        self.r_view = QTextBrowser()
        lay.addWidget(self.r_view, 1)
        self.rep = None
        return w

    def _page_schema(self) -> QWidget:
        self.schema = Schema()
        return self.schema

    # ---------- навігатор ----------
    def refresh_nav(self) -> None:
        self.nav.clear()
        if not self.db:
            return
        objs = {"Таблиці": self.db.tables(), "Запити": list(self.db.objects("query")),
                "Форми": self.db.tables(), "Звіти": list(self.db.objects("report"))}
        ic = {"Таблиці": "table", "Запити": "search", "Форми": "file-lines", "Звіти": "sheet"}
        nm_tables = {r["via"] for r in self.db.relations() if r["kind"] == "N:M"}
        head_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        for b in BLOCKS:
            top = QTreeWidgetItem([f"{b.upper()}   {len(objs[b])}"])
            top.setFont(0, head_font)
            top.setForeground(0, QColor("#135548"))
            top.setIcon(0, icons.icon(ic[b]))
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            top.setSizeHint(0, QSize(0, 34))
            for n in objs[b]:
                it = QTreeWidgetItem([n + ("   ∞—∞" if b == "Таблиці" and n in nm_tables else "")])
                it.setData(0, Qt.ItemDataRole.UserRole, (b, n))
                it.setSizeHint(0, QSize(0, 26))
                top.addChild(it)
            if not objs[b]:
                hint = QTreeWidgetItem(["порожньо — " + {"Запити": "збережіть запит", "Звіти": "збережіть звіт"}.get(b, "створіть таблицю")])
                hint.setForeground(0, QColor("#9aa7a3"))
                hint.setFlags(Qt.ItemFlag.NoItemFlags)
                top.addChild(hint)
            self.nav.addTopLevelItem(top)
            top.setExpanded(True)
        sch = QTreeWidgetItem(["СХЕМА ЗВ'ЯЗКІВ"])
        sch.setFont(0, head_font)
        sch.setForeground(0, QColor("#135548"))
        sch.setIcon(0, icons.icon("merge"))
        sch.setSizeHint(0, QSize(0, 34))
        sch.setData(0, Qt.ItemDataRole.UserRole, ("Схема", ""))
        self.nav.addTopLevelItem(sch)
        self.q_table.blockSignals(True)
        self.q_table.clear()
        self.q_table.addItems(self.db.tables())
        self.q_table.blockSignals(False)
        self._q_fields(self.q_table.currentText())
        self.r_src.blockSignals(True)
        self.r_src.clear()
        self.r_src.addItems([f"Таблиця: {t}" for t in self.db.tables()] + [f"Запит: {n}" for n in self.db.objects("query")])
        self.r_src.blockSignals(False)
        self._r_cols()

    def _nav(self, it: QTreeWidgetItem) -> None:
        d = it.data(0, Qt.ItemDataRole.UserRole)
        if not d:
            return
        kind, name = d
        if kind == "Таблиці":
            self.open_table(name)
        elif kind == "Запити":
            self.open_query(name)
        elif kind == "Форми":
            self.open_form(name)
        elif kind == "Звіти":
            self.open_report(name)
        else:
            self.show_schema()

    def _err(self, e: Exception) -> None:
        QMessageBox.information(self, INTERDATA, str(e))

    # ---------- файли ----------
    def load(self, path: Path) -> None:
        path = Path(path)
        if path.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
            dst = path.with_suffix(".idata")
            self.db = Database.open_sqlite(path, dst)
            path = dst
        elif path.suffix.lower() in (".csv", ".xlsx"):
            dst = path.with_suffix(".idata")
            self.db = Database(dst)
            self._import(path)
            path = dst
        else:
            self.db = Database(path)
        self.path = path
        self.setWindowTitle(f"{path.name} · {INTERDATA}")
        self.refresh_nav()
        if self.db.tables():
            self.open_table(self.db.tables()[0])

    def new_db(self) -> None:
        p = QFileDialog.getSaveFileName(self, "Нова база", "база.idata", "База InterData (*.idata)")[0]
        if p:
            Path(p).unlink(missing_ok=True)
            self.load(Path(p))

    def open_dialog(self) -> None:
        p = QFileDialog.getOpenFileName(self, "Відкрити базу", "", "Бази (*.idata *.db *.sqlite *.sqlite3);;"
                                        "Таблиці (*.csv *.xlsx)")[0]
        if p:
            self.load(Path(p))

    def sample(self, name: str, path: Path | None = None) -> None:
        p = path or QFileDialog.getSaveFileName(self, "Зберегти зразок як", f"{name}.idata", "База InterData (*.idata)")[0]
        if not p:
            return
        Path(p).unlink(missing_ok=True)
        db = Database(p)
        build_sample(db, name)
        db.close()
        self.load(Path(p))

    def _import(self, path: Path) -> None:
        try:
            res = self.db.import_xlsx(path) if path.suffix.lower() == ".xlsx" else {path.stem: self.db.import_csv(path)}
        except DataError as e:
            self._err(e)
            return
        lines = [f"<b>{t}</b>: " + "; ".join(f"{f} — {ty} ({why})" for f, ty, why in rep) for t, rep in res.items()]
        if self.auto_normalize:                       # повтори одразу в довідники (зв'язки замість копій)
            for t in res:
                lines += self._auto_normalize(t)
        self.statusBar().showMessage("Імпортовано: типи й довідники визначено автоматично", 8000)
        self._import_report = "<br>".join(lines)

    auto_normalize = True

    def _auto_normalize(self, tbl: str) -> list[str]:
        out = []
        for h in self.db.normalize_hints(tbl):
            base = h["cols"][0]
            name = base + "и" if not base.endswith(("и", "і", "ї")) else base + " (довідник)"
            if name in self.db.tables():
                name = f"{base} ({tbl})"
            try:
                n = self.db.extract_table(tbl, h["cols"], name)
                out.append(f"<b>Нормалізація:</b> {', '.join(h['cols'])} з «{tbl}» винесено в довідник «{name}» ({n} записів), "
                           f"у «{tbl}» тепер зв'язок. {h['why']}")
            except DataError as e:
                out.append(f"Нормалізацію «{base}» пропущено: {e}")
        return out

    def import_dialog(self) -> None:
        if not self.db:
            self.new_db()
            if not self.db:
                return
        p = QFileDialog.getOpenFileName(self, "Імпорт", "", "Таблиці (*.csv *.xlsx)")[0]
        if p:
            self._import(Path(p))
            self.refresh_nav()
            if getattr(self, "_import_report", ""):
                QMessageBox.information(self, "Типи полів", self._import_report)

    def export(self, kind: str) -> None:
        if not self.db:
            return
        ext = {"xlsx": "XLSX (*.xlsx)", "csv": "CSV (*.csv)", "sql": "SQL (*.sql)"}[kind]
        p = QFileDialog.getSaveFileName(self, "Експорт", f"{self.cur_table or 'база'}.{kind}", ext)[0]
        if not p:
            return
        {"xlsx": lambda: self.db.export_xlsx(Path(p)), "csv": lambda: self.db.export_csv(self.cur_table, Path(p)),
         "sql": lambda: self.db.export_sql(Path(p))}[kind]()
        self.statusBar().showMessage(f"Збережено: {p}", 6000)

    # ---------- таблиці ----------
    def open_table(self, name: str) -> None:
        self.cur_table = name
        self.grid.setSortingEnabled(False)
        self.stack.setCurrentWidget(self.pages["table"])
        fs = self.db.fields(name)
        self._types = {f.name: f.type for f in fs}
        rows = self.db.rows(name)
        self.grid.blockSignals(True)
        fill_table(self.grid, [f.name for f in fs], rows, self._types)
        self.grid.setVerticalHeaderLabels([str(r["id"]) for r in rows])
        for j, f in enumerate(fs):
            tip = TYPES[f.type] + (f" → {f.link}" if f.link else "") + (f": {', '.join(f.choices)}" if f.choices else "") \
                + (f" {f.formula}" if f.formula else "")
            self.grid.horizontalHeaderItem(j).setToolTip(tip)
            if f.type == "formula":
                for i in range(len(rows)):
                    it = self.grid.item(i, j)
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    it.setBackground(QColor("#f4f8f6"))
        self.grid.blockSignals(False)
        self.grid.setSortingEnabled(True)              # сортування кліком по заголовку стовпця
        links = self.db.links_to(name)
        self.t_title.setText(f"<b>{name}</b> — записів: {len(rows)}" +
                             (f"; на неї посилаються: {', '.join(t for t, _ in links)}" if links else ""))
        from ..data.tasks import explain_sql
        last = self.db.history(limit=1)
        self.t_hint.setText(("<b>Остання дія в SQL:</b> <code>" + explain_sql(last[0]).replace("<", "&lt;") + "</code><br>"
                             if last else "") +
                            "Клітинку можна правити прямо в таблиці (значення перевіряється одразу), сортувати — кліком по "
                            "заголовку. Посилання — пишіть назву запису (напр. «5-А»). Формули рахуються самі.")

    def _filter(self, text: str) -> None:
        t = text.lower()
        for i in range(self.grid.rowCount()):
            hit = not t or any(t in (self.grid.item(i, j).text().lower() if self.grid.item(i, j) else "")
                               for j in range(self.grid.columnCount()))
            self.grid.setRowHidden(i, not hit)

    def _cell_edited(self, it: QTableWidgetItem) -> None:
        rid = int(self.grid.verticalHeaderItem(it.row()).text())
        col = self.grid.horizontalHeaderItem(it.column()).text()
        try:
            self.db.update(self.cur_table, rid, {col: it.text()})
            self.statusBar().showMessage(f"Збережено: {col} = {it.text()}", 4000)
        except DataError as e:
            self._err(e)
        self.open_table(self.cur_table)

    def new_table(self) -> None:
        if not self.db:
            self.new_db()
            if not self.db:
                return
        n, ok = QInputDialog.getText(self, "Нова таблиця", "Назва таблиці:")
        if ok and n:
            try:
                self.db.create_table(n, [Field("Назва", required=True)])
                self.refresh_nav()
                self.open_table(n.strip())
            except DataError as e:
                self._err(e)

    def add_row(self) -> None:
        if not self.cur_table:
            return
        try:
            req = [f for f in self.db.fields(self.cur_table) if f.required]
            if req:
                self.open_form(self.cur_table)
                self._f_new()
                return
            self.db.insert(self.cur_table, {})
            self.open_table(self.cur_table)
        except DataError as e:
            self._err(e)

    def del_row(self) -> None:
        r = self.grid.currentRow()
        if not self.cur_table or r < 0:
            return
        self._delete(self.cur_table, int(self.grid.verticalHeaderItem(r).text()))
        self.open_table(self.cur_table)

    def _delete(self, tbl: str, rid: int) -> bool:
        try:
            self.db.delete(tbl, rid)
            return True
        except HasDependents as e:
            box = QMessageBox(QMessageBox.Icon.Question, "Є зв'язані записи", str(e), parent=self)
            clear = box.addButton("Очистити посилання", QMessageBox.ButtonRole.AcceptRole)
            casc = box.addButton("Видалити разом", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() in (clear, casc):
                self.db.delete(tbl, rid, "clear" if box.clickedButton() is clear else "cascade")
                self.statusBar().showMessage("Видалено. «Повернути» (Ctrl+Z) поверне все разом.", 8000)
                return True
        return False

    def undo(self) -> None:
        from ..data.query import restore_snapshot
        if restore_snapshot(self.db):                     # після SQL-пісочниці — назад до знімка
            self.statusBar().showMessage("Повернуто як було до SQL-запиту", 6000)
            if self.cur_table:
                self.open_table(self.cur_table)
            return
        try:
            self.statusBar().showMessage(self.db.undo(), 6000)
            if self.cur_table:
                self.open_table(self.cur_table)
        except DataError as e:
            self._err(e)

    def add_field(self) -> None:
        if not self.cur_table:
            return
        d = FieldDialog(self, self.db, self.cur_table)
        if d.exec():
            try:
                self.db.add_field(self.cur_table, d.field())
                self.refresh_nav()
                self.open_table(self.cur_table)
            except DataError as e:
                self._err(e)

    def change_type(self) -> None:
        c = self.grid.currentColumn()
        if not self.cur_table or c < 0:
            return
        name = self.grid.horizontalHeaderItem(c).text()
        types = [k for k in TYPES if k not in ("link", "formula")]
        t, ok = QInputDialog.getItem(self, "Змінити тип", f"Новий тип поля «{name}»:", [TYPES[k] for k in types], 0, False)
        if not ok:
            return
        nt = types[[TYPES[k] for k in types].index(t)]
        bad = self.db.change_type(self.cur_table, name, nt, dry_run=True)
        if bad:
            QMessageBox.information(self, "Не всі значення підходять",
                                    f"Не підходять {len(bad)} записів: " + ", ".join(f"№{i} «{v}»" for i, v in bad[:10]) +
                                    "\nВиправте їх (або очистіть) і змініть тип ще раз.")
            return
        self.db.change_type(self.cur_table, name, nt)
        self.open_table(self.cur_table)
        self.statusBar().showMessage(f"Тип поля «{name}»: {t}", 6000)

    def normalize(self, ask=None) -> int:
        """Помічник нормалізації: пояснює повтор і виносить поля в окрему таблицю (ask — для тестів)."""
        if not self.cur_table:
            return 0
        hints = self.db.normalize_hints(self.cur_table)
        if not hints:
            self._err(f"У таблиці «{self.cur_table}» повторів, які варто винести, не знайдено.")
            return 0
        done = 0
        for h in hints:
            name = (h["cols"][0] + "и") if not h["cols"][0].endswith(("и", "і")) else h["cols"][0] + " (довідник)"
            q = h["why"] + " Винести " + ", ".join(h["cols"]) + f" у нову таблицю «{name}»?"
            if ask(q) if ask else QMessageBox.question(self, "Нормалізація", q) == QMessageBox.StandardButton.Yes:
                try:
                    n = self.db.extract_table(self.cur_table, h["cols"], name)
                    done += 1
                    self.statusBar().showMessage(f"Створено «{name}» ({n} записів), у «{self.cur_table}» тепер посилання", 8000)
                except DataError as e:
                    self._err(e)
        self.refresh_nav()
        self.open_table(self.cur_table)
        return done

    # ---------- запити ----------
    def _q_fields(self, tbl: str) -> None:
        if not self.db or not tbl:
            return
        names = [f.name for f in self.db.fields(tbl)]
        for f in self.db.fields(tbl):
            if f.type == "link":
                names += [f"{f.name}.{x.name}" for x in self.db.fields(f.link) if x.type != "link"]
        self.q_cols.blockSignals(True)
        self.q_cols.setRowCount(len(names))
        for i, n in enumerate(names):
            ch = QTableWidgetItem()
            ch.setCheckState(Qt.CheckState.Checked if "." not in n else Qt.CheckState.Unchecked)
            self.q_cols.setItem(i, 0, ch)
            nm = QTableWidgetItem(n)
            nm.setFlags(nm.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.q_cols.setItem(i, 1, nm)
            cb = QComboBox()
            for k, v in AGG.items():
                cb.addItem(v or "—", k)
            cb.currentIndexChanged.connect(self._q_live)
            self.q_cols.setCellWidget(i, 2, cb)
        self.q_cols.blockSignals(False)
        self.q_where.blockSignals(True)
        for i in range(self.q_where.rowCount()):
            fcb, ocb = QComboBox(), QComboBox()
            fcb.addItems(["—"] + names)
            ocb.addItems(OPS)
            fcb.currentIndexChanged.connect(self._q_live)
            ocb.currentIndexChanged.connect(self._q_live)
            self.q_where.setCellWidget(i, 0, fcb)
            self.q_where.setCellWidget(i, 1, ocb)
            self.q_where.setItem(i, 2, QTableWidgetItem(""))
        self.q_where.blockSignals(False)
        for cb in (self.q_group, self.q_order):
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(["—"] + names)
            cb.blockSignals(False)
        self._q_live()

    def q_spec(self) -> dict:
        fields = []
        for i in range(self.q_cols.rowCount()):
            if self.q_cols.item(i, 0).checkState() == Qt.CheckState.Checked:
                agg = self.q_cols.cellWidget(i, 2).currentData()
                fields.append({"name": self.q_cols.item(i, 1).text(), **({"agg": agg} if agg else {})})
        where = []
        for i in range(self.q_where.rowCount()):
            f = self.q_where.cellWidget(i, 0).currentText()
            if f != "—":
                where.append({"field": f, "op": self.q_where.cellWidget(i, 1).currentText(),
                              "value": self.q_where.item(i, 2).text() if self.q_where.item(i, 2) else ""})
        s = {"table": self.q_table.currentText(), "fields": fields, "where": where}
        if self.q_group.currentText() != "—":
            s["group"] = [self.q_group.currentText()]
        if self.q_order.currentText() != "—":
            o = self.q_order.currentText()
            agg = next((AGG[c["agg"]] + " " + c["name"] for c in fields if c["name"] == o and c.get("agg")), o)
            s["order"] = [{"field": agg, "desc": self.q_desc.isChecked()}]
        if self.q_limit.value():
            s["limit"] = self.q_limit.value()
        return s

    def _q_live(self, *_):
        if not self.db or not self.q_table.currentText():
            return
        q = Query(self.db, self.q_spec())
        try:
            self.q_sql.setPlainText(q.sql())
            self.q_words.setText(q.words())
            cols, rows = q.run()
            fill_table(self.q_res, cols, rows)
        except (DataError, ValueError, Exception) as e:  # noqa: BLE001
            self.q_words.setText(f"⚠ {e}")

    def new_query(self) -> None:
        if not self.db:
            return
        self.q_name = ""
        self.stack.setCurrentWidget(self.pages["query"])
        self._q_fields(self.q_table.currentText())

    def run_query(self) -> None:
        self.stack.setCurrentWidget(self.pages["query"])
        self._q_live()

    def run_raw_sql(self) -> None:
        import re as _re
        from ..data.query import run_sql_write
        sql = self.q_sql.toPlainText()
        if _re.match(r"^\s*(insert|update|delete)\b", sql, _re.IGNORECASE):
            try:
                n = run_sql_write(self.db, sql)
                self.q_words.setText(f"Виконано: змінено записів — {n}. «Повернути» (Ctrl+Z) поверне базу як було.")
                self.refresh_nav()
            except DataError as e:
                self._err(e)
            return
        try:
            cols, rows = run_sql(self.db, self.q_sql.toPlainText())
            fill_table(self.q_res, cols, rows)
            self.q_words.setText("Виконано SQL, набраний вручну (лише читання).")
        except DataError as e:
            self._err(e)

    def action_query(self, kind: str, field: str | None = None, value: str | None = None, ask=None) -> int:
        """Запит-дія за умовами конструктора: показує SQL і кількість записів, питає підтвердження."""
        from ..data.query import action
        spec = {"table": self.q_table.currentText(), "action": kind, "where": self.q_spec()["where"]}
        if kind == "update":
            if field is None:
                names = [f.name for f in self.db.fields(spec["table"]) if f.type != "formula"]
                field, ok = QInputDialog.getItem(self, "Оновити записи", "Яке поле змінити?", names, 0, False)
                if not ok:
                    return 0
                value, ok = QInputDialog.getText(self, "Оновити записи", f"Нове значення «{field}»:")
                if not ok:
                    return 0
            spec["set"] = {field: value}
        try:
            pv = action(self.db, spec, preview=True)
        except DataError as e:
            self._err(e)
            return 0
        self.q_sql.setPlainText(pv["sql"])
        self.q_words.setText(pv["words"])
        q = pv["words"] + ". Виконати? («Повернути» скасує всю дію)"
        if not (ask(q) if ask else QMessageBox.question(self, "Запит-дія", q) == QMessageBox.StandardButton.Yes):
            return 0
        try:
            res = action(self.db, spec)
        except DataError as e:
            self._err(e)
            return 0
        self.statusBar().showMessage(f"Змінено записів: {res['count']}", 6000)
        self._q_live()
        return res["count"]

    # ---------- навчання ----------
    def add_nm(self, a: str | None = None, b: str | None = None) -> str:
        ts = self.db.tables() if self.db else []
        if len(ts) < 2:
            return ""
        if a is None:
            a, ok = QInputDialog.getItem(self, "Зв'язок ∞—∞", "Перша таблиця:", ts, 0, False)
            if not ok:
                return ""
            b, ok = QInputDialog.getItem(self, "Зв'язок ∞—∞", "Друга таблиця:", [x for x in ts if x != a], 0, False)
            if not ok:
                return ""
        try:
            name = self.db.add_many_to_many(a, b)
        except DataError as e:
            self._err(e)
            return ""
        self.refresh_nav()
        self.open_table(name)
        self.statusBar().showMessage(f"Створено проміжну таблицю «{name}»: кожен рядок — пара {a} ↔ {b}", 8000)
        return name

    def make_task(self, path: str | None = None, title: str | None = None, condition: str | None = None) -> None:
        from ..data.tasks import save_task
        if not self.db:
            return
        if title is None:
            title, ok = QInputDialog.getText(self, "Завдання", "Назва завдання:")
            if not ok:
                return
            condition, ok = QInputDialog.getMultiLineText(self, "Завдання", "Умова для учня:")
            if not ok:
                return
        p = path or QFileDialog.getSaveFileName(self, "Зберегти завдання", f"{title}.itask", "Завдання InterData (*.itask)")[0]
        if not p:
            return
        sql = self.q_sql.toPlainText().strip()
        answer = sql if getattr(self, "_sql_edited", False) else self.q_spec()
        try:
            save_task(self.db, Path(p), title, condition, answer)
            self.statusBar().showMessage(f"Завдання збережено: {p}", 6000)
        except DataError as e:
            self._err(e)

    def load_task(self, path: str | None = None) -> None:
        from ..data.tasks import open_task
        p = path or QFileDialog.getOpenFileName(self, "Відкрити завдання", "", "Завдання InterData (*.itask)")[0]
        if not p:
            return
        self.db, self.task = open_task(Path(p))
        self.path = Path(self.db.path)
        self.refresh_nav()
        self.new_query()
        self.q_words.setText(f"<b>Завдання «{self.task['title']}»:</b> {self.task['condition']}<br>"
                             "Складіть запит у конструкторі або напишіть SQL і натисніть «Перевірити» (F9).")

    def check_task(self) -> bool:
        from ..data.tasks import check
        task = getattr(self, "task", None)
        if not task:
            self._err("Спершу відкрийте завдання (вкладка «Навчання» → «Відкрити»).")
            return False
        sql = self.q_sql.toPlainText().strip()
        student = sql if getattr(self, "_sql_edited", False) else self.q_spec()
        ok, msg = check(self.db, task, student)
        self.q_words.setText(("✅ " if ok else "❌ ") + msg + f"<br><i>Завдання: {task['condition']}</i>")
        return ok

    def save_query(self) -> None:
        n, ok = QInputDialog.getText(self, "Зберегти запит", "Назва запиту:", text=self.q_name)
        if ok and n.strip():
            self.q_name = n.strip()
            self.db.save_object("query", self.q_name, self.q_spec())
            self.refresh_nav()

    def open_query(self, name: str) -> None:
        spec = self.db.objects("query").get(name)
        if not spec:
            return
        self.q_name = name
        self.stack.setCurrentWidget(self.pages["query"])
        self.q_table.setCurrentText(spec["table"])
        self._q_fields(spec["table"])
        want = {c["name"]: c.get("agg", "") for c in spec.get("fields", [])}
        self.q_cols.blockSignals(True)
        for i in range(self.q_cols.rowCount()):
            n = self.q_cols.item(i, 1).text()
            self.q_cols.item(i, 0).setCheckState(Qt.CheckState.Checked if n in want else Qt.CheckState.Unchecked)
            cb = self.q_cols.cellWidget(i, 2)
            cb.setCurrentIndex(max(0, cb.findData(want.get(n, ""))))
        self.q_cols.blockSignals(False)
        for i, w in enumerate(spec.get("where", [])[: self.q_where.rowCount()]):
            self.q_where.cellWidget(i, 0).setCurrentText(w["field"])
            self.q_where.cellWidget(i, 1).setCurrentText(w["op"])
            self.q_where.item(i, 2).setText(str(w.get("value", "")))
        if spec.get("group"):
            self.q_group.setCurrentText(spec["group"][0])
        self.q_limit.setValue(spec.get("limit", 0))
        self._q_live()

    # ---------- форми ----------
    def open_form(self, tbl: str) -> None:
        if not self.db or not tbl:
            return
        self.cur_table = tbl
        self.form = auto_form(self.db, tbl)
        self.stack.setCurrentWidget(self.pages["form"])
        self.f_title.setText(f"Форма «{tbl}»" + (" — зі зв'язаними записами: " + ", ".join(s["table"] for s in self.form["subtables"])
                                                  if self.form["subtables"] else ""))
        while self.f_layout.rowCount():
            self.f_layout.removeRow(0)
        self.f_widgets = {}
        for f in self.db.fields(tbl):
            if f.type in ("choice", "link", "bool"):
                w = QComboBox()
                w.setEditable(f.type == "link")
                items = (f.choices if f.type == "choice" else ["так", "ні"] if f.type == "bool"
                         else [str(r.get(self.db.label_field(f.link))) for r in self.db.rows(f.link)])
                w.addItems([""] + items)
            else:
                w = QLineEdit()
                w.setReadOnly(f.type == "formula")
                if f.type == "date":
                    w.setPlaceholderText("дд.мм.рррр")
            self.f_widgets[f.name] = (f, w)
            lab = f.name + (" *" if f.required else "")
            self.f_layout.addRow(lab, w)
        self.f_ids = [r["id"] for r in self.db.rows(tbl)]
        self.f_i = 0
        self._f_show()

    def _f_show(self) -> None:
        while self.f_subs.count():
            it = self.f_subs.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.f_pos.setText(f"Запис {self.f_i + 1} з {len(self.f_ids)}" if self.f_ids else "Новий запис")
        row = next((r for r in self.db.rows(self.cur_table) if self.f_ids and r["id"] == self.f_ids[self.f_i]), None)
        for name, (f, w) in self.f_widgets.items():
            v = fmt(row.get(name), f.type) if row else ""
            w.setCurrentText(v) if isinstance(w, QComboBox) else w.setText(v)
        if row:
            for s in self.form["subtables"]:
                cols, rows = sub_rows(self.db, s, row["id"])
                t = QTableWidget()
                fill_table(t, cols[1:], [r[1:] for r in rows])
                t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                self.f_subs.addWidget(QLabel(f"<b>{s['table']}</b> ({len(rows)})"))
                self.f_subs.addWidget(t)

    def _f_go(self, d: int) -> None:
        if self.f_ids:
            self.f_i = max(0, min(len(self.f_ids) - 1, self.f_i + d))
            self._f_show()

    def _f_new(self) -> None:
        self.f_ids.append(-1)
        self.f_i = len(self.f_ids) - 1
        for f, w in self.f_widgets.values():
            w.setCurrentText("") if isinstance(w, QComboBox) else w.setText("")
        self.f_pos.setText("Новий запис")

    def _f_values(self) -> dict:
        return {n: (w.currentText() if isinstance(w, QComboBox) else w.text())
                for n, (f, w) in self.f_widgets.items() if f.type != "formula"}

    def _f_save(self) -> None:
        try:
            rid = self.f_ids[self.f_i] if self.f_ids else -1
            if rid == -1:
                rid = self.db.insert(self.cur_table, self._f_values())
                self.f_ids[self.f_i] = rid
            else:
                self.db.update(self.cur_table, rid, self._f_values())
            self.statusBar().showMessage("Запис збережено", 4000)
            self._f_show()
        except DataError as e:
            self._err(e)

    def _f_delete(self) -> None:
        if self.f_ids and self.f_ids[self.f_i] != -1 and self._delete(self.cur_table, self.f_ids[self.f_i]):
            del self.f_ids[self.f_i]
            self.f_i = max(0, self.f_i - 1)
            self._f_show()

    # ---------- звіти ----------
    def _r_source(self) -> dict:
        s = self.r_src.currentText()
        if s.startswith("Запит: "):
            return self.db.objects("query")[s[7:]]
        return {"table": s[len("Таблиця: "):]}

    def _r_cols(self, *_):
        if not self.db or not self.r_src.currentText():
            return
        try:
            cols, _ = Query(self.db, self._r_source()).run()
        except DataError:
            cols = []
        for cb in (self.r_group, self.r_total):
            cb.clear()
            cb.addItems(["—"] + cols)

    def r_spec(self) -> dict:
        s = {"title": self.r_titlebox.text() or self.r_src.currentText().split(": ", 1)[-1], "query": self._r_source()}
        if self.r_group.currentText() != "—":
            s["group"] = self.r_group.currentText()
        if self.r_total.currentText() != "—":
            s["totals"] = {self.r_total.currentText(): self.r_agg.currentData()}
        return s

    def build_report(self) -> None:
        if not self.db:
            return
        self.stack.setCurrentWidget(self.pages["report"])
        try:
            self.rep = report(self.db, self.r_spec())
            self.r_view.setHtml(report_html(self.rep))
        except DataError as e:
            self._err(e)

    def save_report(self) -> None:
        n, ok = QInputDialog.getText(self, "Зберегти звіт", "Назва звіту:", text=self.r_titlebox.text())
        if ok and n.strip():
            self.db.save_object("report", n.strip(), self.r_spec())
            self.refresh_nav()

    def open_report(self, name: str) -> None:
        spec = self.db.objects("report").get(name)
        if spec:
            self.stack.setCurrentWidget(self.pages["report"])
            self.rep = report(self.db, spec)
            self.r_view.setHtml(report_html(self.rep))

    def report_pdf(self, path: str | None = None) -> None:
        if not self.rep:
            self.build_report()
        if not self.rep:
            return
        from PySide6.QtGui import QPageLayout, QPageSize
        from PySide6.QtPrintSupport import QPrinter
        p = path or QFileDialog.getSaveFileName(self, "PDF", f"{self.rep['title']}.pdf", "PDF (*.pdf)")[0]
        if not p:
            return
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pr.setOutputFileName(p)
        pr.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        pr.setPageOrientation(QPageLayout.Orientation.Portrait)
        doc = QTextDocument()
        doc.setHtml(report_html(self.rep))
        doc.print_(pr)
        self.statusBar().showMessage(f"PDF: {p}", 6000)

    def report_export(self, kind: str, path: str | None = None) -> None:
        if not self.rep:
            self.build_report()
        if not self.rep:
            return
        p = path or QFileDialog.getSaveFileName(self, kind.upper(), f"{self.rep['title']}.{kind}", f"{kind.upper()} (*.{kind})")[0]
        if not p:
            return
        if kind == "xlsx":
            report_xlsx(self.rep, p)
        else:
            from ..export.html_docx import html_to_docx
            html_to_docx(report_html(self.rep)).save(p)
        self.statusBar().showMessage(f"Збережено: {p}", 6000)

    # ---------- схема ----------
    def show_schema(self) -> None:
        if self.db:
            self.schema.draw(self.db)
            self.stack.setCurrentWidget(self.pages["schema"])
