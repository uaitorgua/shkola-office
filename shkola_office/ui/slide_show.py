"""InterSlide: режим показу. Клік/пробіл/→ — наступний крок (спершу відповіді за кліком, потім слайд), ← — назад,
Esc — вихід, L — указка, B — чорний екран, T — таймер з нуля. Клік по варіанту квізу — перевірка й бали.
Якщо екранів два: показ на другому, пульт учителя (нотатки, наступний слайд, таймер, бали) — на першому."""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from ..slide.model import Presentation
from ..slide.quiz import check
from .slide_window import paint_element, slide_image


class ShowState:
    def __init__(self, pres: Presentation) -> None:
        self.pres, self.i, self.shown = pres, 0, {}
        self.picked: dict[int, tuple[int, bool]] = {}
        self.score = self.max = 0
        self.t0 = time.monotonic()

    def slide(self):
        return self.pres.slides[self.i]

    def hidden(self) -> list:
        rev = [e for e in self.slide().elements if e.reveal]
        return rev[self.shown.get(self.i, 0):]

    def next(self) -> bool:
        if self.hidden():
            self.shown[self.i] = self.shown.get(self.i, 0) + 1
            return True
        if self.i + 1 < len(self.pres.slides):
            self.i += 1
            return True
        return False

    def prev(self) -> None:
        if self.shown.get(self.i):
            self.shown[self.i] -= 1
        elif self.i:
            self.i -= 1

    def pick(self, opt: int) -> bool | None:
        q = self.slide().quiz
        if not q or q.get("kind") not in ("choice", "truefalse") or self.i in self.picked:
            return None
        ok = check(q, opt)
        self.picked[self.i] = (opt, ok)
        pts = q.get("points", 1)
        self.max += pts
        self.score += pts if ok else 0
        self.shown[self.i] = len([e for e in self.slide().elements if e.reveal])   # одразу показати відповідь
        return ok

    def clock(self) -> str:
        s = int(time.monotonic() - self.t0)
        return f"{s // 60:02d}:{s % 60:02d}"


class SlideShow(QWidget):
    def __init__(self, pres: Presentation, start: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.st = ShowState(pres)
        self.st.i = start
        self.laser = self.black = False
        self.mouse = QPointF()
        self.remote: TeacherPanel | None = None
        self.setWindowTitle("Показ · InterSlide")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.tick = QTimer(self, interval=1000, timeout=self._update)
        self.tick.start()

    # ---------- геометрія ----------
    def _box(self) -> tuple[float, float, float]:
        W, H = self.st.pres.size
        k = min(self.width() / W, self.height() / H)
        return k, (self.width() - W * k) / 2, (self.height() - H * k) / 2

    def _to_slide(self, p: QPointF) -> QPointF:
        k, ox, oy = self._box()
        return QPointF((p.x() - ox) / k, (p.y() - oy) / k)

    # ---------- малювання ----------
    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if self.black:
            return
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        k, ox, oy = self._box()
        st, s = self.st, self.st.slide()
        W, H = st.pres.size
        p.save()
        p.translate(ox, oy)
        p.scale(k, k)
        p.fillRect(QRectF(0, 0, W, H), QColor(s.bg or "#ffffff"))
        hidden = {id(e) for e in st.hidden()}
        for e in s.elements:
            if id(e) not in hidden:
                paint_element(p, e, st.pres)
        if st.i in st.picked:
            opt, ok = st.picked[st.i]
            for e in s.elements:
                if e.role == f"opt:{opt}":
                    p.setPen(QPen(QColor("#2e9d5b" if ok else "#d2453a"), 7))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(QRectF(e.x, e.y, e.w, e.h).adjusted(-4, -4, 4, 4), 14, 14)
        p.restore()
        p.setPen(QColor("#cfd8d5"))
        p.setFont(QFont("Segoe UI", 11))
        info = f"{st.i + 1} / {len(st.pres.slides)}   Час {st.clock()}"
        if st.max:
            info += f"   Бали: {st.score} з {st.max}"
        p.drawText(self.rect().adjusted(12, 6, -12, -6), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, info)
        if self.laser:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(230, 40, 40, 90))
            p.drawEllipse(self.mouse, 16, 16)
            p.setBrush(QColor(255, 40, 40))
            p.drawEllipse(self.mouse, 6, 6)

    def _update(self) -> None:
        self.update()
        if self.remote:
            self.remote.sync()

    # ---------- керування ----------
    def step(self, forward: bool = True) -> None:
        if forward:
            if not self.st.next():
                self.close()
                return
        else:
            self.st.prev()
        self._update()

    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        if k in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown, Qt.Key.Key_Down, Qt.Key.Key_Return):
            self.step(True)
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_Up, Qt.Key.Key_Backspace):
            self.step(False)
        elif k == Qt.Key.Key_Escape:
            self.close()
        elif k == Qt.Key.Key_L:
            self.laser = not self.laser
            self.setCursor(Qt.CursorShape.BlankCursor if self.laser else Qt.CursorShape.ArrowCursor)
        elif k == Qt.Key.Key_B:
            self.black = not self.black
        elif k == Qt.Key.Key_T:
            self.st.t0 = time.monotonic()
        self._update()

    def mouseMoveEvent(self, ev) -> None:
        self.mouse = ev.position()
        if self.laser:
            self.update()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.RightButton:
            self.step(False)
            return
        pt = self._to_slide(ev.position())
        for e in self.st.slide().elements:
            if e.role.startswith("opt:") and QRectF(e.x, e.y, e.w, e.h).contains(pt):
                if self.st.pick(int(e.role[4:])) is not None:
                    self._update()
                    return
        self.step(True)

    def closeEvent(self, ev) -> None:
        if self.remote:
            self.remote.close()
        super().closeEvent(ev)


class TeacherPanel(QWidget):
    """Пульт учителя: поточний і наступний слайд, нотатки, таймер, бали."""

    def __init__(self, show: SlideShow) -> None:
        super().__init__()
        self.show_ = show
        self.setWindowTitle("Пульт учителя · InterSlide")
        self.cur, self.nxt, self.info = QLabel(), QLabel(), QLabel()
        self.info.setStyleSheet("font-size:22px;font-weight:700;color:#135548")
        self.notes = QPlainTextEdit(readOnly=True)
        self.notes.setStyleSheet("font-size:18px")
        row = QHBoxLayout()
        row.addWidget(self.cur)
        col = QVBoxLayout()
        col.addWidget(QLabel("Далі:"))
        col.addWidget(self.nxt)
        col.addStretch(1)
        row.addLayout(col)
        lay = QVBoxLayout(self)
        lay.addWidget(self.info)
        lay.addLayout(row)
        lay.addWidget(self.notes, 1)
        self.sync()

    def sync(self) -> None:
        st = self.show_.st
        self.cur.setPixmap(QPixmap.fromImage(slide_image(st.pres, st.slide(), 560)))
        if st.i + 1 < len(st.pres.slides):
            self.nxt.setPixmap(QPixmap.fromImage(slide_image(st.pres, st.pres.slides[st.i + 1], 280)))
        else:
            self.nxt.setText("Кінець презентації")
        left = len(st.hidden())
        self.info.setText(f"Слайд {st.i + 1} з {len(st.pres.slides)}   Час {st.clock()}"
                          + (f"   Бали: {st.score} з {st.max}" if st.max else "")
                          + (f"   Прихованих відповідей: {left}" if left else ""))
        self.notes.setPlainText(st.slide().notes or "—")

    def keyPressEvent(self, ev) -> None:
        self.show_.keyPressEvent(ev)


def start_show(pres: Presentation, start: int = 0) -> SlideShow:
    show = SlideShow(pres, start)
    screens = QGuiApplication.screens()
    if len(screens) > 1:
        show.setGeometry(screens[1].geometry())
        show.remote = TeacherPanel(show)
        show.remote.setGeometry(screens[0].availableGeometry())
        show.remote.show()
    show.showFullScreen()
    show.activateWindow()
    return show
