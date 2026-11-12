"""Збірка Windows-EXE «Офіс ШКОЛА»: тести → іконка → PyInstaller → перевірка запуску → підпис ГС «УАІТ».
python tools/build.py [notest] [nosign]
Підпис: tools/sign.ps1 зі «Сканера ШКОЛА» (ключ certs/*.pfx лежить лише там, поза цим публічним репозиторієм);
інший шлях — змінна SHKOLA_SIGN_PS1."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
args = {a.lower() for a in sys.argv[1:]}
EXE = ROOT / "dist" / "OfisShkola.exe"
SIGN = Path(os.environ.get("SHKOLA_SIGN_PS1") or ROOT.parent / "Сканер-ШКОЛА" / "tools" / "sign.ps1")
TESTS = ["test_editors", "test_doc_pages", "test_sheet_extra", "test_interslide", "test_slide_themes",
         "test_slide_library", "test_slide_quiz", "test_slide_scenarios", "test_interdata_core", "test_interdata_ui", "test_ownfmt_autosave", "test_all_buttons", "test_update"]


def run(title: str, cmd: list[str]) -> None:
    print(f"== {title}", flush=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": "C:/Windows/Fonts", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(cmd, cwd=ROOT, env=env if "tests" in " ".join(cmd) else None)
    if r.returncode:
        sys.exit(f"[ПОМИЛКА] «{title}» завершився з кодом {r.returncode}")


def make_icon() -> Path:
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QGuiApplication, QImage, QPainter, Qt
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    ico = ROOT / "build" / "ofis.ico"
    ico.parent.mkdir(exist_ok=True)
    img = QImage(256, 256, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    QSvgRenderer(QByteArray((ROOT / "shkola_office" / "assets" / "logo.svg").read_bytes())).render(p)
    p.end()
    img.save(str(ico), "ICO")
    return ico


if "notest" not in args:
    for t in TESTS:
        run(f"Тест {t}", [PY, f"tests/{t}.py"])
if EXE.exists():
    try:
        open(EXE, "r+b").close()
    except PermissionError:
        sys.exit("[ПОМИЛКА] dist/OfisShkola.exe відкритий — закрийте «Офіс ШКОЛА».")
ico = make_icon()
sys.path.insert(0, str(ROOT))
from shkola_office import __version__  # noqa: E402
run("PyInstaller", [PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
                    "--name", "OfisShkola", "--icon", str(ico),
                    "--collect-submodules", "shkola_office", "--add-data", "shkola_office/assets;shkola_office_assets",
                    "--add-data", "LICENSE.txt;.",
                    "--collect-submodules", "docx", "--collect-data", "docx", "--collect-submodules", "pptx",
                    "--collect-data", "pptx", "--collect-submodules", "openpyxl", "--hidden-import", "PySide6.QtSvg",
                    "--hidden-import", "PySide6.QtPrintSupport",
                    *[x for m in ("tkinter", "matplotlib", "pandas", "scipy", "torch", "cv2", "IPython", "numba",
                                  "PySide6.QtWebEngineCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia",
                                  "PySide6.Qt3DCore") for x in ("--exclude-module", m)],
                    "main.py"])
print("== Перевірка запуску EXE", flush=True)
proc = subprocess.Popen([str(EXE)])
time.sleep(10)
alive = proc.poll() is None
subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
time.sleep(1.5)
if not alive:
    sys.exit(f"[ПОМИЛКА] EXE завершився з кодом {proc.returncode}")
print("EXE запускається й тримається 10 с")
if "nosign" not in args:
    if SIGN.exists():
        run("Підпис сертифікатом ГС «УАІТ»", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                               str(SIGN), "-ExePath", str(EXE)])
    else:
        print(f"[!] Скрипт підпису не знайдено ({SIGN}) — EXE не підписано")
print(f"\nГОТОВО: {EXE}  {__version__}  ({EXE.stat().st_size / 1e6:.1f} МБ)")
