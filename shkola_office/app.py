"""Застосунок «Офіс ШКОЛА»: стартове вікно з InterText, InterTab, InterSlide і нещодавніми файлами.
Запуск: python main.py [файл] [--intertext|--intertab|--interslide]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QApplication, QFileDialog, QGridLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QToolButton, QVBoxLayout, QWidget)

from . import __version__, config
from .ui import icons
from .ui.banner import Banner
from .ui.logo import app_icon

EDITORS = {  # ключ: (назва, підпис, іконка, розширення)
    "text": ("InterText", "Документи: накази, листи, плани\nDOCX · PDF · друк", "file-lines", (".docx", ".itext", ".html", ".htm", ".txt")),
    "tab": ("InterTab", "Таблиці: журнали, табелі, розклад\nXLSX · CSV · формули", "table", (".xlsx", ".itab", ".csv")),
    "slide": ("InterSlide", "Презентації, уроки й квізи\nPPTX · PDF · HTML-квіз", "image", (".islide",)),
    "data": ("InterData", "База даних: таблиці, запити,\nформи, звіти · SQLite", "sheet", (".idata", ".db", ".sqlite")),
}
RECENT = config.DATA_DIR / "recent.json"
FILTER = "Файли Офісу ШКОЛА (*.docx *.itext *.html *.htm *.txt *.xlsx *.itab *.csv *.islide *.idata *.db *.sqlite);;Усі файли (*)"


APP_ICONS = config.OFFICE_ASSETS / "app-icons"
ICON_ID = {"text": "intertext", "tab": "intertab", "slide": "interslide", "data": "interdata"}


def app_icon_for(k: str):
    from PySide6.QtGui import QIcon
    f = APP_ICONS / f"{ICON_ID.get(k, 'ofis')}.svg"
    return QIcon(str(f)) if f.exists() else app_icon()


def kind_of(path: Path) -> str | None:
    suf = path.suffix.lower()
    return next((k for k, v in EDITORS.items() if suf in v[3]), None)


def _recent() -> list[str]:
    try:
        return [p for p in json.loads(RECENT.read_text(encoding="utf-8")) if Path(p).exists()][:12]
    except (OSError, ValueError):
        return []


def remember(path) -> None:
    items = [str(path)] + [p for p in _recent() if p != str(path)]
    try:
        RECENT.parent.mkdir(parents=True, exist_ok=True)
        RECENT.write_text(json.dumps(items[:12], ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class StartWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(900, 700)
        self.windows: list = []
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 12)
        lay.addWidget(Banner(config.APP_NAME, "ДОКУМЕНТИ · ТАБЛИЦІ · ПРЕЗЕНТАЦІЇ · БАЗИ ДАНИХ · ДЛЯ ШКОЛИ", compact=False))
        grid = QGridLayout()
        grid.setContentsMargins(24, 16, 24, 0)
        grid.setSpacing(16)
        for i, (k, (name, sub, ic, _)) in enumerate(EDITORS.items()):
            b = QToolButton()
            b.setObjectName("tile")
            b.setText(f"{name}\n{sub}")
            b.setIcon(app_icon_for(k))
            b.setIconSize(QSize(64, 64))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setMinimumSize(380, 130)
            b.clicked.connect(lambda _=False, k=k: self.open_editor(k))
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        bar = QWidget()
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(24, 10, 24, 0)
        op = QToolButton(text="Відкрити файл…")
        op.setObjectName("open")
        op.clicked.connect(self.open_dialog)
        bl.addWidget(op, 0, Qt.AlignmentFlag.AlignLeft)
        bl.addWidget(QLabel("Нещодавні файли"))
        self.recent = QListWidget()
        self.recent.itemActivated.connect(lambda it: self.open_path(Path(it.data(Qt.ItemDataRole.UserRole))))
        bl.addWidget(self.recent, 1)
        lay.addWidget(bar, 1)
        self.setCentralWidget(box)
        self.setStyleSheet("""
            QWidget{background:#f6faf8} QToolButton#tile{background:#ffffff;border:1px solid #cfe3dc;border-radius:14px;
            padding:14px;font-size:14px;color:#1f2d2a} QToolButton#tile:hover{border:2px solid #1d7a66;background:#eef7f3}
            QToolButton#open{background:#135548;color:#fff;border-radius:8px;padding:8px 16px;font-size:14px}
            QListWidget{background:#fff;border:1px solid #dbe7e2;border-radius:8px;font-size:13px}
            QLabel{color:#5b6b67;font-size:13px;margin-top:8px}""")
        self.fill_recent()

    def offer_restore(self, ask=None) -> int:
        """Після збою: незбережені документи з автозбереження — відновити чи забути."""
        from .ui import autosave
        n = 0
        for item in autosave.pending():
            when = __import__("time").strftime("%d.%m %H:%M", __import__("time").localtime(item["time"]))
            name = Path(item["path"]).name if item["path"] else "новий документ"
            q = f"Знайдено незбережену роботу: {name} ({EDITORS[item['kind']][0]}, {when}). Відновити?"
            yes = ask(q) if ask else QMessageBox.question(self, config.APP_NAME, q) == QMessageBox.StandardButton.Yes
            if yes:
                w = self._make(item["kind"])
                w.load(item["backup"])
                w.path = Path(item["path"]) if item["path"] else None
                if hasattr(w, "_touch"):
                    w._touch()
                elif hasattr(w, "edit"):
                    w.edit.document().setModified(True)
                else:
                    w.setWindowModified(True)
                w.show()
                n += 1
            autosave.forget(item)
        return n

    def fill_recent(self) -> None:
        self.recent.clear()
        for p in _recent():
            k = kind_of(Path(p))
            it = QListWidgetItem(f"{Path(p).name}   —   {EDITORS[k][0] if k else ''}   ·   {Path(p).parent}")
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.recent.addItem(it)

    def _make(self, k: str):
        if k == "text":
            from .ui.editor_window import EditorWindow
            w = EditorWindow(None, "", "Документ")
        elif k == "tab":
            from .ui.sheet_window import SheetWindow
            w = SheetWindow()
        elif k == "slide":
            from .ui.slide_window import SlideWindow
            w = SlideWindow()
        else:
            from .ui.data_window import DataWindow
            w = DataWindow()
        w.setWindowIcon(app_icon_for(k))
        if hasattr(w, "saved"):
            w.saved.connect(lambda p: (remember(p), self.fill_recent()))
        self.windows.append(w)
        return w

    def open_editor(self, k: str):
        w = self._make(k)
        w.show()
        w.raise_()
        return w

    def open_path(self, path: Path):
        k = kind_of(path)
        if not k or not path.exists():
            QMessageBox.information(self, config.APP_NAME, f"Не вдалося відкрити: {path}")
            return None
        w = self._make(k)
        w.load(path)
        w.show()
        remember(path)
        self.fill_recent()
        return w

    def open_dialog(self) -> None:
        p = QFileDialog.getOpenFileName(self, "Відкрити", "", FILTER)[0]
        if p:
            self.open_path(Path(p))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName("ГС «УАІТ»")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    start = StartWindow()
    files = [Path(a) for a in argv if not a.startswith("--")]
    mode = {"--intertext": "text", "--intertab": "tab", "--interslide": "slide", "--interdata": "data"}
    flag = next((mode[a] for a in argv if a in mode), None)
    if files:
        start.open_path(files[0])
    elif flag:
        start.open_editor(flag)
    else:
        start.show()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(400, start.offer_restore)
    # Обов'язкова перевірка оновлень — лише в самостійній програмі (main), не в редакторах усередині Сканера
    from .ui.update_check import UpdateChecker
    start._updates = UpdateChecker(start)
    QTimer.singleShot(1500, start._updates.start)
    return app.exec()
