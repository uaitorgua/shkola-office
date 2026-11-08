"""Власні SVG-іконки ГС «УАІТ» (shkola_office/assets/icons, генерує tools/make_icons.py).
Основний колір перефарбовується за станом кнопки, бурштиновий акцент лишається."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from ..config import OFFICE_ASSETS
from . import theme

SVG_DIR = OFFICE_ASSETS / "icons"
SVG_MAIN = "#135548"


def available() -> bool:
    return SVG_DIR.is_dir()


@lru_cache(maxsize=256)
def _svg_src(name: str) -> str | None:
    f = SVG_DIR / f"{name}.svg"
    return f.read_text(encoding="utf-8") if f.exists() else None


@lru_cache(maxsize=1024)
def _svg(name: str, s: int, col: str) -> QPixmap:
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    src = _svg_src(name).replace(SVG_MAIN, col)
    if col == "#a9b4b0":
        src = src.replace("#f0b14a", col)
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(src.encode("utf-8"))).render(p)
    p.end()
    return pm


@lru_cache(maxsize=256)
def _svg_src(name: str) -> str | None:
    f = SVG_DIR / f"{name}.svg"
    return f.read_text(encoding="utf-8") if f.exists() else None


@lru_cache(maxsize=1024)
def _svg(name: str, s: int, col: str) -> QPixmap:
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    src = _svg_src(name).replace(SVG_MAIN, col)
    if col == "#a9b4b0":
        src = src.replace("#f0b14a", col)
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(src.encode("utf-8"))).render(p)
    p.end()
    return pm


def family() -> str | None:
    global _family
    if _family is None and FONT_FILE.exists():
        fid = QFontDatabase.addApplicationFont(str(FONT_FILE))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        _family = fams[0] if fams else ""
    return _family or None


@lru_cache(maxsize=512)
def icon(name: str, color: str = theme.PRIMARY_DARK, size: int = 20) -> QIcon:
    """Звичайний стан — зелений (гама застосунку), увімкнений — графіт на бурштиновому тлі кнопки,
    вимкнений — сірий."""
    ic = QIcon()
    if _svg_src(name):
        for s in (size, size * 2):
            ic.addPixmap(_svg(name, s, color), QIcon.Mode.Normal, QIcon.State.Off)
            ic.addPixmap(_svg(name, s, theme.TEXT), QIcon.Mode.Normal, QIcon.State.On)
            ic.addPixmap(_svg(name, s, theme.TEXT), QIcon.Mode.Active, QIcon.State.On)
            ic.addPixmap(_svg(name, s, "#a9b4b0"), QIcon.Mode.Disabled, QIcon.State.Off)
        return ic
    return ic


def decorate(window, mapping: dict[str, str], keep_text: bool = True) -> None:
    """Ставить іконки діям панелей вікна за їхнім текстом: {текст дії: назва іконки}.
    keep_text=False → лише іконка (текст лишається у підказці)."""
    from PySide6.QtWidgets import QToolBar
    if not available():
        return
    for tb in window.findChildren(QToolBar):
        for a in tb.actions():
            name = mapping.get(a.text())
            if name:
                a.setIcon(icon(name))
                if not keep_text:
                    if not a.toolTip() or a.toolTip() == a.text():
                        a.setToolTip(a.text())
                    a.setIconText("")
                    a.setText("")
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if keep_text
                              else Qt.ToolButtonStyle.ToolButtonIconOnly)
