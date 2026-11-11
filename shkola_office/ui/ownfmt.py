"""Власні формати «Офісу ШКОЛА» — zip із JSON: зберігають усе, що губиться в типових форматах.
.itext (InterText): document.html + images/ + meta.json (поля сторінки, колонтитули).
.itab (InterTab): sheets.json (сирі значення й формули, формати, ширини, об'єднання, закріплення, підсвітка, діаграми).
Типові формати (DOCX/XLSX/PDF/CSV) лишаються для обміну: «Зберегти» пише в той формат, з яким працюють."""
from __future__ import annotations

import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

ITEXT, ITAB = ".itext", ".itab"


# ---------- InterText ----------
def write_itext(win, path: Path) -> None:
    st = win.edit.setup
    meta = {"format": "itext-1", "setup": [st.left, st.right, st.top, st.bottom], "hf": asdict(win.hf)}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("document.html", win.html())
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False))
        for name, data in win._images_png().items():
            z.writestr("images/" + name.replace("/", "_"), data)


def read_itext(win, path: Path) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    from .doc_pages import HeaderFooter
    from .editor_page import PageSetup
    with zipfile.ZipFile(path) as z:
        html = z.read("document.html").decode("utf-8")
        meta = json.loads(z.read("meta.json").decode("utf-8"))
        for n in z.namelist():
            if n.startswith("images/") and len(n) > 7:
                img = QImage.fromData(z.read(n))
                if not img.isNull():
                    win.edit.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(n[7:]), img)
    win.edit.setup = PageSetup(*meta.get("setup", [30, 10, 20, 20]))
    win.hf = HeaderFooter(**meta.get("hf", {}))
    win.set_html(html)


# ---------- InterTab ----------
def _sheet_state(w) -> dict:
    spans = []
    cells = ((r, c) for r in range(min(w.rowCount(), 1000)) for c in range(min(w.columnCount(), 100)))
    for (r, c) in cells:
        rs, cs = w.rowSpan(r, c), w.columnSpan(r, c)
        if (rs > 1 or cs > 1) and [r, c, rs, cs] not in spans:
            spans.append([r, c, rs, cs])
    charts = [{k: v for k, v in asdict(ch).items() if k != "image"} for ch in getattr(w, "charts", [])]
    return {"raw": [[r, c, v] for (r, c), v in w.raw.items()],
            "fmt": [[r, c, f] for (r, c), f in w.fmt.items()],
            "widths": {str(c): w.columnWidth(c) for c in range(w.columnCount()) if w.columnWidth(c) != 100},
            "spans": spans, "freeze": w.freeze, "cond": [asdict(x) for x in w.cond], "charts": charts}


def write_itab(win, path: Path) -> None:
    data = {"format": "itab-1", "sheets": [{"name": win.tabs.tabText(i), **_sheet_state(win.tabs.widget(i))}
                                           for i in range(win.tabs.count())]}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("sheets.json", json.dumps(data, ensure_ascii=False))


def read_itab(win, path: Path) -> None:
    from .sheet_extra import CondRule
    with zipfile.ZipFile(path) as z:
        data = json.loads(z.read("sheets.json").decode("utf-8"))
    win.tabs.clear()
    for s in data["sheets"]:
        raw = {(r, c): v for r, c, v in s["raw"]}
        nr = max((r for r, _ in raw), default=-1) + 1
        nc = max((c for _, c in raw), default=-1) + 1
        rows = [[raw.get((r, c), "") for c in range(nc)] for r in range(nr)]
        fmts = {(r, c): f for r, c, f in s.get("fmt", [])}
        fmts["__merges__"] = [tuple(x) for x in s.get("spans", [])]
        fmts["__widths__"] = {int(k): v for k, v in s.get("widths", {}).items()}
        fmts["__freeze__"] = s.get("freeze", 0)
        fmts["__charts__"] = [SimpleNamespace(**ch) for ch in s.get("charts", [])]
        sh = win.add_sheet(s["name"], rows, fmts)
        sh.cond = [CondRule(**x) for x in s.get("cond", [])]
        sh.recalc()
    win.tabs.setCurrentIndex(0)
