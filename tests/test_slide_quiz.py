"""InterSlide етап 4: 5 видів квізу, відповідь за кліком, показ (кроки, бали), PPTX/PDF розгортають відповідь,
HTML-квіз (один файл, перевірка логіки в Chromium через Playwright, якщо є)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
import fitz  # noqa: E402
from pptx import Presentation as PP  # noqa: E402

from shkola_office.slide.quiz import make_quiz_slide  # noqa: E402
from shkola_office.ui.slide_show import ShowState, SlideShow  # noqa: E402
from shkola_office.ui.slide_window import QuizDialog, SlideWindow  # noqa: E402

D = Path(os.environ.get("ISLIDE_OUT") or tempfile.mkdtemp())
w = SlideWindow()
w.resize(1300, 800)
Q = [{"kind": "choice", "question": "Столиця України?", "options": ["Львів", "Київ", "Харків", "Одеса"], "answer": [1], "points": 2},
     {"kind": "truefalse", "question": "Вода кипить за 100 °C на рівні моря.", "answer": [0]},
     {"kind": "input", "question": "Дріб ½ читається як одна …", "answer": "друга", "options": ["третя", "ціла"]},
     {"kind": "order", "question": "Упорядкуйте від меншого", "options": ["1/4", "1/3", "1/2"]},
     {"kind": "match", "question": "Знайдіть пару", "options": [["H₂O", "вода"], ["NaCl", "сіль"], ["O₂", "кисень"]]}]
for q in Q:
    w.add_slide(make_quiz_slide(w.pres, q))
d = QuizDialog(w, "choice")
d.q.setText("2+2?")
d.opts.setPlainText("3\n*4\n5")
assert d.quiz()["answer"] == [1] and d.quiz()["options"] == ["3", "4", "5"]
d = QuizDialog(w, "match")
d.opts.setPlainText("а = б\nв = г")
assert d.quiz()["options"] == [["а", "б"], ["в", "г"]]
n = len(w.pres.slides)
assert n == 6 and all(any(e.reveal for e in s.elements) for s in w.pres.slides[1:])
order = w.pres.slides[4].quiz
assert order["shown"] != order["options"], "перемішано"

# показ
st = ShowState(w.pres)
assert st.next() and st.i == 1                       # титул → квіз 1
assert len(st.hidden()) == 1
assert st.pick(0) is False and st.pick(1) is None    # друга спроба не рахується
assert st.score == 0 and st.max == 2 and not st.hidden()
assert st.next() and st.i == 2 and st.pick(0) is True and st.score == 1
assert st.next() and st.i == 3 and st.hidden() and st.next() and not st.hidden()    # відповідь за кліком
show = SlideShow(w.pres, 1)
show.resize(1280, 720)
show.show()
app.processEvents()
k, ox, oy = show._box()
opt = [e for e in w.pres.slides[1].elements if e.role == "opt:1"][0]
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtCore import QEvent  # noqa: E402
pos = QPointF(ox + (opt.x + 10) * k, oy + (opt.y + 10) * k)
show.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, pos, pos, Qt.MouseButton.LeftButton,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
assert show.st.picked[1] == (1, True) and show.st.score == 2
show.grab().save(str(D / "show.png"))
show.close()

# експорт
assert w.save_to(D / "q.pptx") and len(PP(str(D / "q.pptx")).slides) == n + 5
assert w.save_to(D / "q.pdf")
doc = fitz.open(str(D / "q.pdf"))
assert len(doc) == n + 5 and "Відповідь" not in doc[1].get_text() and "Відповідь: Б) Київ" in doc[2].get_text()
assert w.save_to(D / "q.html")
h = (D / "q.html").read_text(encoding="utf-8")
assert "Столиця України?" in h and "http" not in h.split("<script>")[0].replace("http-equiv", "")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((D / "q.html").as_uri())
        qs = pg.locator(".q")
        qs.nth(0).locator("button.o").nth(1).click()          # Київ
        qs.nth(1).locator("button.o").nth(0).click()          # Правда
        qs.nth(2).locator(".tile", has_text="друга").click()
        shown = pg.evaluate("Q[3].shown")
        for j, item in enumerate(shown):
            qs.nth(3).locator("select").nth(j).select_option(str(["1/4", "1/3", "1/2"].index(item) + 1))
        right = pg.evaluate("Q[4].shown")
        for j, r in enumerate(["вода", "сіль", "кисень"]):
            qs.nth(4).locator("select").nth(j).select_option(str(right.index(r)))
        pg.click("#go")
        res = pg.inner_text("#res")
        pg.screenshot(path=str(D / "quiz_html.png"), full_page=True)
        b.close()
    assert not errs, errs
    assert res.startswith("Результат: 6 з 6"), res
    print("HTML-квіз у браузері:", res)
w.grab().save(str(D / "quiz_window.png"))
print("КВІЗИ Й ПОКАЗ OK", D)
