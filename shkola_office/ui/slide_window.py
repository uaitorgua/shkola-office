"""InterSlide: вікно редактора презентацій. Один рендерер paint_element() малює полотно, мініатюри й PDF."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QMarginsF, QPointF, QRectF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QImage, QPainter, QPageLayout, QPageSize, QPdfWriter, QPixmap, QTextOption
from PySide6.QtWidgets import (QColorDialog, QFileDialog, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
                               QInputDialog, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                               QSplitter, QToolButton, QVBoxLayout, QWidget)

from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDockWidget, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QSpinBox)

from ..config import APP_NAME
from ..slide import library
from ..slide.model import Element, Presentation, Slide, export_pptx, static_slides
from ..slide.quiz import KINDS, export_html, make_quiz_slide
from ..slide.scenarios import SCENARIOS, build as build_scenario
from ..slide.themes import LAYOUTS, THEMES, apply_theme, lib_element, make_slide, new_presentation
from .banner import Banner
from .logo import app_icon
from .ribbon import RIBBON_STYLE, Ribbon
from .shapes import SHAPES, draw_shape

INTERSLIDE = "InterSlide"
HANDLE = 10


def paint_element(p: QPainter, e: Element, pres: Presentation, r: QRectF | None = None) -> None:
    r = r or QRectF(e.x, e.y, e.w, e.h)
    if e.kind == "image" and e.media.lower().endswith(".svg"):
        QSvgRenderer(QByteArray(pres.media.get(e.media, b""))).render(p, r)
        return
    if e.kind == "image":
        img = QImage.fromData(pres.media.get(e.media, b""))
        if not img.isNull():
            p.drawImage(r, img)
        return
    if e.kind == "shape":
        img = draw_shape(e.shape, max(1, int(r.width())), max(1, int(r.height())), e.fill or "#1d7a66",
                         e.line or e.fill or "#135548", scale=2)
        p.drawImage(r.adjusted(-1, -1, 1, 1), img)
    elif e.fill:
        p.fillRect(r, QColor(e.fill))
    if e.text:
        f = QFont(e.font or pres.font)
        f.setPixelSize(max(1, int(e.size)))
        f.setBold(e.bold)
        f.setItalic(e.italic)
        p.setFont(f)
        p.setPen(QColor(e.color))
        al = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
              "right": Qt.AlignmentFlag.AlignRight}.get(e.align, Qt.AlignmentFlag.AlignLeft)
        card = e.kind == "shape" and e.align == "left"            # картка з текстом: зверху, з полями
        opt = QTextOption(al)
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        pad = 18 if card else 6
        box = r.adjusted(pad, pad if card else 4, -pad, -pad)
        if e.kind == "shape" and not card:                       # по вертикалі — по центру
            h = p.fontMetrics().boundingRect(box.toRect(), int(al) | int(Qt.TextFlag.TextWordWrap), e.text).height()
            box.setTop(box.top() + max(0, (box.height() - h) / 2))
        p.drawText(box, e.text, opt)


def paint_slide(p: QPainter, pres: Presentation, s: Slide) -> None:
    W, H = pres.size
    p.fillRect(QRectF(0, 0, W, H), QColor(s.bg or "#ffffff"))
    for e in s.elements:
        paint_element(p, e, pres)


def slide_image(pres: Presentation, s: Slide, width: int = 192) -> QImage:
    W, H = pres.size
    img = QImage(width, int(width * H / W), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(width / W, width / W)
    paint_slide(p, pres, s)
    p.end()
    return img


def svg_png(data: bytes, w: int, h: int) -> bytes:
    img = QImage(max(1, w), max(1, h), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    QSvgRenderer(QByteArray(data)).render(p)
    p.end()
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def export_pdf(pres: Presentation, path: Path) -> None:
    W, H = pres.size
    w = QPdfWriter(str(path))
    w.setResolution(72)
    w.setPageSize(QPageSize(QSizeF(W, H), QPageSize.Unit.Point))
    w.setPageMargins(QMarginsF(0, 0, 0, 0))
    w.setTitle(pres.title or INTERSLIDE)
    p = QPainter(w)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = w.width() / W
    for i, s in enumerate(static_slides(pres)):
        if i:
            w.newPage()
        p.save()
        p.scale(k, k)
        paint_slide(p, pres, s)
        p.restore()
    p.end()


class ElemItem(QGraphicsRectItem):
    """Елемент на полотні: тягнути — переміщення, кут унизу праворуч — розмір, подвійний клік — текст."""

    def __init__(self, e: Element, win: "SlideWindow") -> None:
        super().__init__(0, 0, e.w, e.h)
        self.e, self.win = e, win
        self.setPos(e.x, e.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                      | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._resizing = False

    def paint(self, p, opt, w=None) -> None:
        paint_element(p, self.e, self.win.pres, self.rect())
        if self.isSelected():
            p.setPen(QColor("#d08a12"))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self.rect())
            p.setBrush(QColor("#d08a12"))
            p.drawRect(QRectF(self.rect().right() - HANDLE, self.rect().bottom() - HANDLE, HANDLE, HANDLE))
        if self.e.reveal:                                       # позначка «за кліком»
            p.setPen(QColor("#d08a12"))
            p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            p.drawText(self.rect().adjusted(0, -18, 0, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "за кліком")
        if not self.isSelected() and self.e.kind == "text" and not self.e.text:
            p.setPen(QColor("#b9c4c0"))
            p.drawRect(self.rect())

    def _in_handle(self, pos: QPointF) -> bool:
        r = self.rect()
        return pos.x() > r.right() - HANDLE * 1.5 and pos.y() > r.bottom() - HANDLE * 1.5

    def hoverMoveEvent(self, ev) -> None:
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if self._in_handle(ev.pos()) else Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, ev) -> None:
        self._resizing = self.isSelected() and self._in_handle(ev.pos())
        super().mousePressEvent(ev) if not self._resizing else ev.accept()

    def mouseMoveEvent(self, ev) -> None:
        if self._resizing:
            self.prepareGeometryChange()
            self.setRect(0, 0, max(20, ev.pos().x()), max(16, ev.pos().y()))
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        super().mouseReleaseEvent(ev)
        self._resizing = False
        self.sync()

    def mouseDoubleClickEvent(self, ev) -> None:
        if self.e.kind != "image":
            self.win.edit_text(self)

    def sync(self) -> None:
        self.e.x, self.e.y = round(self.pos().x(), 1), round(self.pos().y(), 1)
        self.e.w, self.e.h = round(self.rect().width(), 1), round(self.rect().height(), 1)
        self.win.changed()


class Canvas(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QColor("#e9eeec"))
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if self.scene():
            self.fitInView(self.scene().sceneRect().adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)


class SlideWindow(QMainWindow):
    saved = Signal(str)

    def __init__(self, parent=None, pres: Presentation | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{INTERSLIDE} · {APP_NAME}")
        self.setWindowIcon(app_icon())
        self.resize(1280, 800)
        self.setStyleSheet(RIBBON_STYLE)
        self.path: Path | None = None
        self.pres = pres or new_presentation()
        self.cur = 0
        self.thumbs = QListWidget()
        self.thumbs.setIconSize(QSize(176, 99))
        self.thumbs.setFixedWidth(210)
        self.thumbs.currentRowChanged.connect(self.show_slide)
        self.canvas = Canvas()
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Нотатки вчителя до слайда (у PPTX — нотатки доповідача)")
        self.notes.setMaximumHeight(90)
        self.notes.textChanged.connect(self._notes)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.canvas, 1)
        rl.addWidget(self.notes)
        sp = QSplitter()
        sp.addWidget(self.thumbs)
        sp.addWidget(right)
        sp.setStretchFactor(1, 1)
        self.setCentralWidget(sp)
        self._ribbon()
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        tl.addWidget(Banner(INTERSLIDE, "ПРЕЗЕНТАЦІЇ · УРОКИ · КВІЗИ · PPTX · PDF", compact=True))
        tl.addWidget(self.ribbon)
        self.setMenuWidget(top)
        self._library()
        self.refresh(0)

    # ---------- бібліотека ----------
    def _library(self) -> None:
        dock = QDockWidget("Бібліотека", self)
        dock.setObjectName("library")
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        self.lib_find = QLineEdit()
        self.lib_find.setPlaceholderText("Пошук: книга, атом, свято…")
        self.lib_topic = QComboBox()
        self.lib_topic.addItem("Усі теми", "")
        for t in library.topics():
            self.lib_topic.addItem(t, t)
        self.lib_list = QListWidget()
        self.lib_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.lib_list.setIconSize(QSize(56, 56))
        self.lib_list.setGridSize(QSize(84, 84))
        self.lib_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lib_list.setMovement(QListWidget.Movement.Static)
        self.lib_list.itemDoubleClicked.connect(lambda it: self.add_lib(it.data(Qt.ItemDataRole.UserRole)))
        lay.addWidget(self.lib_find)
        lay.addWidget(self.lib_topic)
        lay.addWidget(self.lib_list, 1)
        dock.setWidget(box)
        dock.setMinimumWidth(290)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.lib_dock = dock
        self.lib_find.textChanged.connect(self.fill_library)
        self.lib_topic.currentIndexChanged.connect(self.fill_library)
        self.fill_library()

    def fill_library(self) -> None:
        self.lib_list.clear()
        theme = THEMES.get(self.pres.theme)
        for it in library.search(self.lib_find.text(), self.lib_topic.currentData() or ""):
            pm = QPixmap(QSize(112, 112))
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            QSvgRenderer(QByteArray(library.themed_svg(it, theme if theme and theme.bg == "#ffffff" else None))).render(p)
            p.end()
            w = QListWidgetItem(pm, it["title"])
            w.setToolTip(f'{it["title"]} · {it["topic"]} · {it["tags"]}')
            w.setData(Qt.ItemDataRole.UserRole, it)
            self.lib_list.addItem(w)

    def add_lib(self, item: dict) -> None:
        self.add_elem(lib_element(self.pres, item))

    # ---------- стрічка ----------
    def _ribbon(self) -> None:
        rb = Ribbon(self)
        self.ribbon = rb
        mb = self.menuBar()
        f = mb.addMenu("Файл")
        for t, k, s in (("Нова презентація", "Ctrl+N", self.new), ("Відкрити…", "Ctrl+O", self.open_dialog),
                        ("Зберегти", "Ctrl+S", self.save), ("Зберегти як…", "Ctrl+Shift+S", self.save_as)):
            a = f.addAction(t, s)
            a.setShortcut(k)
        f.addSeparator()
        f.addAction("Експорт у PPTX…", lambda: self.save_as("pptx"))
        f.addAction("Експорт у PDF…", lambda: self.save_as("pdf"))
        f.addAction("HTML-квіз для учнів…", lambda: self.save_as("html"))
        sc = f.addMenu("Нова за сценарієм")
        for name in SCENARIOS:
            sc.addAction(name, lambda n=name: self.from_scenario(n))
        sl = rb.tab("Слайди")
        g = sl.group("Новий")
        g.big("Титул", "new", lambda: self.add_layout("Титул"))
        b = g.big("Макет", "plus", None, tip="Новий слайд за макетом уроку")
        m = QMenu(self)
        for k in LAYOUTS:
            m.addAction(k, lambda k=k: self.add_layout(k))
        self._popup(g, b, m)
        g.big("Ще такий", "copy", lambda: self.add_layout(self.slide().layout or "Два стовпці"), key="Ctrl+M",
              tip="Новий слайд із тим самим макетом")
        b = g.big("Сценарій", "wand", None, tip="Готова презентація: урок, квіз, збори, педрада, виховна година, свято")
        m2 = QMenu(self)
        for name in SCENARIOS:
            m2.addAction(name, lambda n=name: self.from_scenario(n))
        self._popup(g, b, m2)
        g = sl.group("Упорядкувати")
        g.column(g.action("Дублювати", "copy", self.dup_slide), g.action("Видалити", "trash", self.del_slide))
        g.column(g.action("Вище", "sort-up", lambda: self.move_slide(-1)),
                 g.action("Нижче", "sort-down", lambda: self.move_slide(1)))
        g = sl.group("Слайд")
        g.big("Тло", "fill", self.slide_bg)
        g.column(g.action("16:9", "expand", lambda: self.set_ratio("16:9")),
                 g.action("4:3", "crop", lambda: self.set_ratio("4:3")))
        ad = rb.tab("Додати")
        g = ad.group("Об'єкти")
        g.big("Текст", "text", lambda: self.add_elem(Element("text", 80, 80, 400, 60, "Текст", 24)))
        b = g.big("Фігура", "layers", None)
        m = QMenu(self)
        for k in SHAPES:
            m.addAction(k, lambda k=k: self.add_elem(Element("shape", 120, 120, 220, 140, shape=k, fill="#1d7a66", align="center",
                                                              color="#ffffff")))
        self._popup(g, b, m)
        g.big("Зображення", "image", self.add_image)
        g.big("Бібліотека", "book", lambda: self.lib_dock.setVisible(not self.lib_dock.isVisible()),
              tip="Шкільні векторні об'єкти за темами: подвійний клік — на слайд")
        qz = rb.tab("Квіз")
        g = qz.group("Нове питання")
        for k, (title, ic) in {"choice": ("Вибір", "list-ol"), "truefalse": ("Правда чи ні", "check"),
                               "input": ("Вписати", "edit"), "order": ("Упорядкувати", "sort-down"),
                               "match": ("Пари", "merge")}.items():
            g.big(title, ic, lambda k=k: self.quiz_dialog(k))
        g = qz.group("Відповідь")
        g.big("За кліком", "eye", self.toggle_reveal,
              tip="Виділений елемент з'являється в показі лише за кліком (відповідь, підказка)")
        g = qz.group("Для учнів")
        g.big("HTML-квіз", "file-import", lambda: self.save_as("html"),
              tip="Один файл із питаннями квізу: учень відкриває в браузері, без інтернету")
        g = qz.group("Показ")
        g.big("З початку", "eye", lambda: self.slideshow(0), key="F5")
        g.big("З цього", "arrow-right", lambda: self.slideshow(self.cur), key="Shift+F5")
        dz = rb.tab("Дизайн")
        g = dz.group("Тема")
        for name in THEMES:
            g.big(name, "palette", lambda n=name: self.set_theme(n), tip="Перефарбувати всі слайди в тему")
        fm = rb.tab("Формат")
        g = fm.group("Текст")
        g.column(g.action("Жирний", "bold", lambda: self._fmt(bold=None)),
                 g.action("Курсив", "italic", lambda: self._fmt(italic=None)))
        g.column(g.action("Більше", "zoom-in", lambda: self._fmt(size=+4)),
                 g.action("Менше", "zoom-out", lambda: self._fmt(size=-4)))
        g.column(g.action("Ліворуч", "align-left", lambda: self._fmt(align="left")),
                 g.action("По центру", "align-center", lambda: self._fmt(align="center")),
                 g.action("Праворуч", "align-right", lambda: self._fmt(align="right")))
        g = fm.group("Колір")
        g.column(g.action("Колір тексту", "font", lambda: self._color("color")),
                 g.action("Заливка", "paint", lambda: self._color("fill")))
        g = fm.group("Шар")
        g.column(g.action("Наперед", "arrow-right", lambda: self._z(1)), g.action("Назад", "arrow-left", lambda: self._z(-1)))
        g.big("Видалити", "trash", self.del_elems, key="Delete")
        rb.finish(mb)

    def _popup(self, g, act, menu) -> None:
        for btn in g.findChildren(QToolButton):
            if btn.defaultAction() is act:
                btn.setMenu(menu)
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def add_layout(self, name: str) -> None:
        self.add_slide(make_slide(name, self.pres))

    def set_theme(self, name: str) -> None:
        apply_theme(self.pres, name)
        self.refresh()
        self.fill_library()
        self.setWindowModified(True)

    def from_scenario(self, name: str) -> None:
        if self.isWindowModified() and QMessageBox.question(
                self, INTERSLIDE, "Замінити поточну презентацію сценарієм? Незбережені зміни зникнуть.")                 != QMessageBox.StandardButton.Yes:
            return
        self.pres, self.path = build_scenario(name, self.pres.ratio), None
        self.refresh(0)
        self.fill_library()
        self.setWindowModified(False)

    # ---------- квіз і показ ----------
    def quiz_dialog(self, kind: str) -> None:
        d = QuizDialog(self, kind)
        if d.exec():
            q = d.quiz()
            if q:
                self.add_slide(make_quiz_slide(self.pres, q))

    def toggle_reveal(self) -> None:
        for it in self.selected():
            it.e.reveal = not it.e.reveal
            it.update()
        self.changed()

    def slideshow(self, start: int = 0):
        from .slide_show import start_show
        self._show = start_show(self.pres, start)
        return self._show

    # ---------- стан ----------
    def slide(self) -> Slide:
        return self.pres.slides[self.cur]

    def selected(self) -> list[ElemItem]:
        sc = self.canvas.scene()
        return [i for i in (sc.selectedItems() if sc else []) if isinstance(i, ElemItem)]

    def refresh(self, row: int | None = None) -> None:
        row = self.cur if row is None else row
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for i, s in enumerate(self.pres.slides):
            it = QListWidgetItem(str(i + 1))
            it.setIcon(QPixmap.fromImage(slide_image(self.pres, s, 176)))
            self.thumbs.addItem(it)
        self.thumbs.blockSignals(False)
        self.thumbs.setCurrentRow(max(0, min(row, len(self.pres.slides) - 1)))
        self.show_slide(self.thumbs.currentRow())

    def show_slide(self, i: int) -> None:
        if i < 0 or i >= len(self.pres.slides):
            return
        self.cur = i
        W, H = self.pres.size
        sc = QGraphicsScene(0, 0, W, H)
        bg = sc.addRect(0, 0, W, H, Qt.PenStyle.NoPen, QColor(self.slide().bg or "#ffffff"))
        bg.setZValue(-1)
        for e in self.slide().elements:
            sc.addItem(ElemItem(e, self))
        self.canvas.setScene(sc)
        self.canvas.fitInView(QRectF(-20, -20, W + 40, H + 40), Qt.AspectRatioMode.KeepAspectRatio)
        self.notes.blockSignals(True)
        self.notes.setPlainText(self.slide().notes)
        self.notes.blockSignals(False)

    def changed(self) -> None:
        it = self.thumbs.item(self.cur)
        if it:
            it.setIcon(QPixmap.fromImage(slide_image(self.pres, self.slide(), 176)))
        self.setWindowModified(True)

    def _notes(self) -> None:
        self.slide().notes = self.notes.toPlainText()

    # ---------- слайди ----------
    def add_slide(self, s: Slide) -> None:
        self.pres.slides.insert(self.cur + 1, s)
        self.refresh(self.cur + 1)

    def dup_slide(self) -> None:
        self.add_slide(Slide.from_dict(self.pres.to_json()["slides"][self.cur]))

    def del_slide(self) -> None:
        if len(self.pres.slides) > 1:
            del self.pres.slides[self.cur]
            self.refresh(self.cur - 1 if self.cur else 0)

    def move_slide(self, d: int) -> None:
        j = self.cur + d
        if 0 <= j < len(self.pres.slides):
            s = self.pres.slides
            s[self.cur], s[j] = s[j], s[self.cur]
            self.refresh(j)

    def set_ratio(self, ratio: str) -> None:
        (ow, _), self.pres.ratio = self.pres.size, ratio
        k = self.pres.size[0] / ow
        for s in self.pres.slides:
            for e in s.elements:
                e.x, e.w = e.x * k, e.w * k
        apply_theme(self.pres, self.pres.theme)
        self.refresh()

    def slide_bg(self) -> None:
        c = QColorDialog.getColor(QColor(self.slide().bg), self, "Тло слайда")
        if c.isValid():
            self.slide().bg = c.name()
            self.show_slide(self.cur)
            self.changed()

    # ---------- елементи ----------
    def add_elem(self, e: Element) -> ElemItem:
        self.slide().elements.append(e)
        it = ElemItem(e, self)
        self.canvas.scene().addItem(it)
        self.canvas.scene().clearSelection()
        it.setSelected(True)
        self.changed()
        return it

    def add_image(self, path: str | None = None) -> None:
        path = path or QFileDialog.getOpenFileName(self, "Зображення", "", "Зображення (*.png *.jpg *.jpeg *.svg *.webp)")[0]
        if not path:
            return
        data = Path(path).read_bytes()
        img = QImage.fromData(data)
        W, H = self.pres.size
        w, h = (img.width(), img.height()) if not img.isNull() else (300, 200)
        k = min(1.0, W * 0.6 / w, H * 0.6 / h)
        self.add_elem(Element("image", (W - w * k) / 2, (H - h * k) / 2, w * k, h * k,
                              media=self.pres.add_media(Path(path).name, data)))

    def edit_text(self, it: ElemItem) -> None:
        t, ok = QInputDialog.getMultiLineText(self, "Текст", "Текст елемента:", it.e.text)
        if ok:
            it.e.text = t
            it.update()
            self.changed()

    def _fmt(self, **kw) -> None:
        for it in self.selected():
            e = it.e
            for k, v in kw.items():
                if k in ("bold", "italic"):
                    setattr(e, k, not getattr(e, k))
                elif k == "size":
                    e.size = max(8, e.size + v)
                else:
                    setattr(e, k, v)
            it.update()
        self.changed()

    def _color(self, attr: str) -> None:
        its = self.selected()
        if its:
            c = QColorDialog.getColor(QColor(getattr(its[0].e, attr) or "#ffffff"), self)
            if c.isValid():
                for it in its:
                    setattr(it.e, attr, c.name())
                    it.update()
                self.changed()

    def _z(self, d: int) -> None:
        els = self.slide().elements
        for it in self.selected():
            i = els.index(it.e)
            j = max(0, min(len(els) - 1, i + d))
            els.insert(j, els.pop(i))
        self.show_slide(self.cur)
        self.changed()

    def del_elems(self) -> None:
        for it in self.selected():
            self.slide().elements.remove(it.e)
            self.canvas.scene().removeItem(it)
        self.changed()

    # ---------- файли ----------
    def new(self) -> None:
        self.pres, self.path = new_presentation(self.pres.theme or "Мінімал ГС"), None
        self.refresh(0)

    def load(self, path: Path) -> None:
        self.pres, self.path = Presentation.load(Path(path)), Path(path)
        self.setWindowTitle(f"{self.path.name} · {INTERSLIDE}")
        self.refresh(0)

    def open_dialog(self) -> None:
        p = QFileDialog.getOpenFileName(self, "Відкрити", "", "Презентація InterSlide (*.islide)")[0]
        if p:
            self.load(Path(p))

    def save_to(self, path: Path) -> bool:
        path = Path(path)
        try:
            suf = path.suffix.lower()
            if suf == ".pptx":
                export_pptx(self.pres, path, raster=svg_png)
            elif suf == ".pdf":
                export_pdf(self.pres, path)
            elif suf in (".html", ".htm"):
                if not export_html(self.pres, path):
                    QMessageBox.information(self, INTERSLIDE, "У презентації немає слайдів-квізів (вкладка «Квіз»).")
                    return False
            else:
                self.pres.save(path)
                self.path = path
                self.setWindowModified(False)
        except Exception as ex:  # noqa: BLE001
            QMessageBox.warning(self, INTERSLIDE, f"Не вдалося зберегти:\n{ex}")
            return False
        self.statusBar().showMessage(f"Збережено: {path}")
        self.saved.emit(str(path))
        return True

    def save(self) -> None:
        self.save_to(self.path) if self.path else self.save_as()

    def save_as(self, kind: str = "islide") -> None:
        flt = {"islide": "Презентація InterSlide (*.islide)", "pptx": "Презентація PPTX (*.pptx)", "pdf": "PDF (*.pdf)",
               "html": "HTML-квіз (*.html)"}[kind]
        p = QFileDialog.getSaveFileName(self, "Зберегти", f"презентація.{kind}", flt)[0]
        if p:
            self.save_to(Path(p))


class QuizDialog(QDialog):
    HINTS = {"choice": "Варіанти — кожен з нового рядка; правильні позначте * на початку. Напр.: *Київ",
             "truefalse": "Правильна відповідь:",
             "input": "Перший рядок — правильне слово; далі слова-підказки для плиток (необов'язково).",
             "order": "Елементи в ПРАВИЛЬНОМУ порядку, кожен з нового рядка (у слайді перемішаються).",
             "match": "Пари через «=», кожна з нового рядка. Напр.: Київ = Україна"}

    def __init__(self, parent, kind: str) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"Квіз · {KINDS[kind]}")
        self.q = QLineEdit()
        self.q.setPlaceholderText("Текст запитання")
        self.opts = QPlainTextEdit()
        self.tf = QComboBox()
        self.tf.addItems(["Правда", "Неправда"])
        self.pts = QSpinBox(minimum=1, maximum=12, value=1)
        lay = QFormLayout(self)
        lay.addRow("Запитання:", self.q)
        lay.addRow(QLabel(self.HINTS[kind]))
        lay.addRow(self.tf if kind == "truefalse" else self.opts)
        lay.addRow("Бали:", self.pts)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)
        self.resize(520, 360)

    def quiz(self) -> dict | None:
        lines = [x.strip() for x in self.opts.toPlainText().splitlines() if x.strip()]
        q = {"kind": self.kind, "question": self.q.text().strip() or "Питання", "points": self.pts.value()}
        if self.kind == "truefalse":
            q["answer"] = [self.tf.currentIndex()]
        elif self.kind == "choice":
            q["options"] = [x.lstrip("*").strip() for x in lines]
            q["answer"] = [i for i, x in enumerate(lines) if x.startswith("*")] or [0]
        elif self.kind == "input":
            if not lines:
                return None
            q["answer"], q["options"] = lines[0], lines[1:]
        elif self.kind == "order":
            q["options"] = lines
        else:
            q["options"] = [[a.strip(), b.strip()] for a, b in (x.split("=", 1) for x in lines if "=" in x)]
        if self.kind in ("choice", "order", "match") and len(q["options"]) < 2:
            return None
        return q
