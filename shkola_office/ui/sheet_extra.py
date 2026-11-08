"""InterTab: фільтр за значеннями, закріплення верхніх рядків, умовне форматування (з пресетом для 12-бальних
оцінок), шкільні шаблони таблиць."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHeaderView,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QTableView, QVBoxLayout)


# ---------- умовне форматування ----------
@dataclass
class CondRule:
    r0: int
    c0: int
    r1: int
    c1: int
    op: str            # ">", "<", ">=", "<=", "=", "<>", "між", "містить"
    a: str
    b: str = ""
    color: str = "#fde2e1"

    def hit(self, v) -> bool:
        from .sheet_model import to_number
        if v in (None, ""):
            return False
        if self.op == "містить":
            return self.a.lower() in str(v).lower()
        x = to_number(str(v)) if not isinstance(v, (int, float)) else v
        a = to_number(self.a)
        if self.op == "між":
            b = to_number(self.b)
            try:
                return min(a, b) <= x <= max(a, b)
            except TypeError:
                return False
        try:
            return {">": x > a, "<": x < a, ">=": x >= a, "<=": x <= a, "=": x == a, "<>": x != a}[self.op]
        except TypeError:
            return str(x) == str(a) if self.op == "=" else (str(x) != str(a) if self.op == "<>" else False)

    def contains(self, r: int, c: int) -> bool:
        return self.r0 <= r <= self.r1 and self.c0 <= c <= self.c1


COLORS = {"Червоне тло": "#fde2e1", "Жовте тло": "#fff3c4", "Зелене тло": "#dcf3e6", "Блакитне тло": "#dde9fb"}
OPS = [">", "<", ">=", "<=", "=", "<>", "між", "містить"]


def apply_cond(sheet) -> None:
    """Після recalc: перше правило, що спрацювало, фарбує тло комірки."""
    for rule in getattr(sheet, "cond", []):
        for r in range(rule.r0, min(rule.r1, sheet.rowCount() - 1) + 1):
            for c in range(rule.c0, min(rule.c1, sheet.columnCount() - 1) + 1):
                it = sheet.item(r, c)
                if it is not None and (r, c) in sheet.raw and rule.hit(sheet.value(r, c)):
                    it.setBackground(QBrush(QColor(rule.color)))


def grades_preset(sheet, r0, c0, r1, c1) -> None:
    """12-бальна шкала: 1–3 червоне, 4–6 жовте, 10–12 зелене."""
    sheet.cond += [CondRule(r0, c0, r1, c1, "між", "1", "3", COLORS["Червоне тло"]),
                   CondRule(r0, c0, r1, c1, "між", "4", "6", COLORS["Жовте тло"]),
                   CondRule(r0, c0, r1, c1, "між", "10", "12", COLORS["Зелене тло"])]
    sheet.recalc()


class CondDialog(QDialog):
    def __init__(self, parent, rng: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Підсвітити комірки за умовою")
        f = QFormLayout(self)
        self.op = QComboBox()
        self.op.addItems(OPS)
        self.a = QLineEdit()
        self.b = QLineEdit()
        self.b.setPlaceholderText("лише для «між»")
        self.col = QComboBox()
        self.col.addItems(COLORS)
        f.addRow("Діапазон", QLineEdit(rng, readOnly=True))
        f.addRow("Умова", self.op)
        f.addRow("Значення", self.a)
        f.addRow("До", self.b)
        f.addRow("Колір", self.col)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def rule(self, r0, c0, r1, c1) -> CondRule:
        return CondRule(r0, c0, r1, c1, self.op.currentText(), self.a.text().strip(), self.b.text().strip(),
                        COLORS[self.col.currentText()])


# ---------- фільтр ----------
class FilterDialog(QDialog):
    def __init__(self, parent, values: list[str], hidden: set[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Фільтр стовпця")
        lay = QVBoxLayout(self)
        self.lst = QListWidget()
        for v in values:
            it = QListWidgetItem(v or "(порожні)")
            it.setData(Qt.ItemDataRole.UserRole, v)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked if v in hidden else Qt.CheckState.Checked)
            self.lst.addItem(it)
        lay.addWidget(self.lst)
        b_all = QPushButton("Позначити всі")
        b_all.clicked.connect(lambda: [self.lst.item(i).setCheckState(Qt.CheckState.Checked) for i in range(self.lst.count())])
        lay.addWidget(b_all)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def shown(self) -> set[str]:
        return {self.lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lst.count())
                if self.lst.item(i).checkState() == Qt.CheckState.Checked}


def last_row(sheet) -> int:
    return max((r for r, _c in sheet.raw), default=-1)


def filter_column(sheet, c: int, keep: set[str], header: int = 1) -> int:
    """Ховає рядки (нижче заголовка), значення яких у стовпці c не в keep. Повертає кількість схованих."""
    n = 0
    for r in range(header, last_row(sheet) + 1):
        v = sheet.item(r, c).text() if sheet.item(r, c) else ""
        hide = v not in keep
        sheet.setRowHidden(r, hide)
        n += hide
    sheet.filter_col = c if n else None
    return n


def clear_filter(sheet) -> None:
    for r in range(sheet.rowCount()):
        sheet.setRowHidden(r, False)
    sheet.filter_col = None


# ---------- закріплення верхніх рядків ----------
class _Frozen(QTableView):
    def __init__(self, sheet) -> None:
        super().__init__(sheet)
        self.sheet = sheet
        self.setModel(sheet.model())
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.verticalHeader().setFixedWidth(sheet.verticalHeader().width())
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionModel(sheet.selectionModel())
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setStyleSheet("QTableView { border: none; border-bottom: 2px solid #f0b14a; background: white; }")
        sheet.horizontalScrollBar().valueChanged.connect(self.horizontalScrollBar().setValue)
        sheet.horizontalHeader().sectionResized.connect(lambda i, _o, n: self.setColumnWidth(i, n))
        for j in range(sheet.columnCount()):
            self.setColumnWidth(j, sheet.columnWidth(j))

    def place(self, n: int) -> None:
        s = self.sheet
        self.verticalHeader().setFixedWidth(s.verticalHeader().width())
        h = s.horizontalHeader().height() + sum(s.rowHeight(r) for r in range(n))
        self.setGeometry(s.frameWidth(), s.frameWidth(), s.viewport().width() + s.verticalHeader().width(), h)
        for r in range(s.rowCount()):
            self.setRowHidden(r, r >= n)
            if r < n:
                self.setRowHeight(r, s.rowHeight(r))


def freeze_rows(sheet, n: int) -> None:
    """Закріплює n верхніх рядків (0 — зняти): вони лишаються видимими під час прокручування."""
    sheet.freeze = n
    fr = getattr(sheet, "_frozen", None)
    if n <= 0:
        if fr:
            fr.hide()
        return
    if fr is None:
        fr = sheet._frozen = _Frozen(sheet)
        old = sheet.resizeEvent

        def resized(e, _old=old):
            _old(e)
            if sheet.freeze:
                sheet._frozen.place(sheet.freeze)
        sheet.resizeEvent = resized
    fr.place(n)
    fr.show()
    fr.raise_()


# ---------- шаблони ----------
def _journal():
    head = ["№", "Прізвище, ім'я"] + [f"{d:02d}.09" for d in range(1, 11)] + ["Середній бал"]
    rows = [head]
    for i in range(1, 11):
        r = i + 1
        rows.append([str(i), f"[Учень {i}]"] + [""] * 10 + [f'=IF(COUNT(C{r}:L{r})=0;"";ROUND(AVERAGE(C{r}:L{r});1))'])
    return rows


def _tabel():
    subj = ["Українська мова", "Математика", "Англійська мова", "Історія", "Фізкультура"]
    rows = [["№", "Прізвище, ім'я"] + subj + ["Середній", "Мінімум"]]
    for i in range(1, 11):
        r = i + 1
        rows.append([str(i), f"[Учень {i}]"] + [""] * len(subj) + [f'=IF(COUNT(C{r}:G{r})=0;"";ROUND(AVERAGE(C{r}:G{r});1))',
                                                                   f'=IF(COUNT(C{r}:G{r})=0;"";MIN(C{r}:G{r}))'])
    rows.append(["", "Середній по класу"] + [f'=IF(COUNT({c}2:{c}11)=0;"";ROUND(AVERAGE({c}2:{c}11);1))' for c in "CDEFG"] + ["", ""])
    return rows


def _attendance():
    rows = [["№", "Прізвище, ім'я"] + [f"{d:02d}" for d in range(1, 16)] + ["Пропущено (н)"]]
    for i in range(1, 11):
        r = i + 1
        rows.append([str(i), f"[Учень {i}]"] + [""] * 15 + [f'=COUNTIF(C{r}:Q{r};"н")'])
    return rows


def _schedule():
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]
    return [["Урок", "Час"] + days] + [[str(i), t] + [""] * 5 for i, t in enumerate(
        ["08:30–09:15", "09:25–10:10", "10:30–11:15", "11:35–12:20", "12:30–13:15", "13:25–14:10", "14:20–15:05"], 1)]


TEMPLATES = {
    "Журнал оцінок": (_journal, (1, 2, 10, 11)),          # (будівник, діапазон оцінок для підсвічування)
    "Табель успішності": (_tabel, (1, 2, 10, 6)),
    "Облік відвідування": (_attendance, None),
    "Розклад уроків": (_schedule, None),
}
