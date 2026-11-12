"""MSIX «Офіс ШКОЛА» для Microsoft Store з dist/OfisShkola.exe (Store підписує пакет сам).
Іконки — з shkola_office/assets/app-icons/ofis.svg (кожен розмір окремим рендером). Запуск: python packaging/make_msix.py"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
STAGE = ROOT / "build" / "msix"
OUT = ROOT / "dist" / "OfisShkola.msix"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
SVG = ROOT / "shkola_office" / "assets" / "app-icons" / "ofis.svg"
BG = "#1b1f8a"


def tool(name: str) -> Path:
    found = sorted(SDK.glob(f"*/x64/{name}"))
    if not found:
        sys.exit(f"Не знайдено {name}. Встановіть Windows SDK.")
    return found[-1]


def assets(out: Path) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    r = QSvgRenderer(str(SVG))

    def png(name: str, w: int, h: int | None = None, icon: int | None = None, bg: str | None = None) -> None:
        h = h or w
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(QColor(bg) if bg else Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = icon or w
        r.render(p, QRectF((w - s) / 2, (h - s) / 2, s, s))
        p.end()
        img.save(str(out / name))

    png("Square44x44Logo.png", 44)
    for s in (16, 24, 32, 48, 256):
        for suf in ("", "_altform-unplated", "_altform-lightunplated"):
            png(f"Square44x44Logo.targetsize-{s}{suf}.png", s)
    png("Square150x150Logo.png", 150)
    png("StoreLogo.png", 50)
    png("Wide310x150Logo.png", 310, 150, 120, BG)
    png("SplashScreen.png", 620, 300, 240, BG)


def main() -> None:
    ident = json.loads((PKG / "store_identity.json").read_text(encoding="utf-8"))
    exe = ROOT / "dist" / "OfisShkola.exe"
    if not exe.exists():
        sys.exit("Спершу python tools/build.py")
    shutil.rmtree(STAGE, ignore_errors=True)
    (STAGE / "Assets").mkdir(parents=True)
    shutil.copy2(exe, STAGE)
    assets(STAGE / "Assets")
    manifest = (PKG / "AppxManifest.template.xml").read_text(encoding="utf-8")
    for k, v in ident.items():
        manifest = manifest.replace("{" + k + "}", v)
    (STAGE / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    cfg = ROOT / "build" / "priconfig.xml"
    subprocess.run([str(tool("makepri.exe")), "createconfig", "/cf", str(cfg), "/dq", "uk-UA", "/o"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([str(tool("makepri.exe")), "new", "/pr", str(STAGE), "/cf", str(cfg), "/of", str(STAGE / "resources.pri"),
                    "/mn", str(STAGE / "AppxManifest.xml"), "/o"], check=True, stdout=subprocess.DEVNULL)
    OUT.unlink(missing_ok=True)
    subprocess.run([str(tool("makeappx.exe")), "pack", "/d", str(STAGE), "/p", str(OUT), "/o"], check=True,
                   stdout=subprocess.DEVNULL)
    print(f"MSIX: {OUT}  ({OUT.stat().st_size / 1e6:.1f} МБ)")


if __name__ == "__main__":
    main()
