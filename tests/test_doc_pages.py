"""Етап 3: колонтитули (PDF, DOCX), зміст, шаблони."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from shkola_office.ui.editor_window import EditorWindow
from shkola_office.ui.doc_pages import TEMPLATES, HeaderFooter

w = EditorWindow()
w.set_html("".join(f"<h1>Розділ {i}</h1>" + "<p>текст абзацу</p>" * 40 for i in range(1, 4)))
b = w.edit.document().begin()
while b.isValid():  # set_html може не нести headingLevel — ставимо явно
    if b.text().startswith("Розділ"):
        c = w.edit.textCursor(); c.setPosition(b.position()); w.edit.setTextCursor(c); w._set_heading(1)
    b = b.next()
c = w.edit.textCursor(); c.setPosition(0); w.edit.setTextCursor(c)
w._toc()
assert "ЗМІСТ" in w.edit.toPlainText() and "Розділ 3\t" in w.edit.toPlainText(), "зміст"
w.hf = HeaderFooter(footer="Сторінка {стор} з {усього}", skip_first=False)
d = Path(tempfile.mkdtemp())
assert w.save_to(d / "t.pdf") and w.save_to(d / "t.docx")
import zipfile
x = zipfile.ZipFile(d / "t.docx").read("word/footer1.xml").decode() if "word/footer1.xml" in zipfile.ZipFile(d / "t.docx").namelist() else \
    "".join(zipfile.ZipFile(d / "t.docx").read(n).decode() for n in zipfile.ZipFile(d / "t.docx").namelist() if "footer" in n)
assert "PAGE" in x and "NUMPAGES" in x, "поля в DOCX"
import fitz
pdf = fitz.open(str(d / "t.pdf"))
n = len(pdf)
assert n >= 2 and f"Сторінка 2 з {n}" in pdf[1].get_text(), "колонтитул у PDF"
print("PDF сторінок:", n)
for name in TEMPLATES:
    w.edit.document().setModified(False)
    w._template(name)
    assert "[" in w.edit.toPlainText(), name
print("ЕТАП 3 OK")
