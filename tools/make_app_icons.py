"""Іконки застосунків «Офісу ШКОЛА» у стилі сімейства ШКОЛА (Сканер, Накази, Принтер, Розклад):
синій квадрат зі скругленням і градієнтом, білий предмет, бірюзовий/зелений акцент, бузкові деталі.
→ shkola_office/assets/app-icons/<id>.svg (+ .png 256). Запуск: python tools/make_app_icons.py"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "shkola_office" / "assets" / "app-icons"
BG = ('<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b3fb8"/>'
      '<stop offset="1" stop-color="#1b1f8a"/></linearGradient></defs>'
      '<rect x="8" y="8" width="240" height="240" rx="52" fill="url(#g)"/>')
TEAL, GREEN, LIL, W = "#19c3b0", "#3ccf6e", "#c3c6e6", "#ffffff"

ICONS = {
    # документ: аркуш із загином, бірюзовий заголовок, бузкові рядки
    "intertext": (f'<path d="M80 44h70l38 38v124a10 10 0 0 1-10 10H80a10 10 0 0 1-10-10V54a10 10 0 0 1 10-10z" fill="{W}"/>'
                  f'<path d="M150 44v30a8 8 0 0 0 8 8h30" fill="#e3e5f5"/>'
                  f'<rect x="88" y="98" width="62" height="12" rx="6" fill="{TEAL}"/>'
                  + "".join(f'<rect x="88" y="{y}" width="{w}" height="9" rx="4.5" fill="{LIL}"/>'
                            for y, w in ((126, 82), (146, 82), (166, 82), (186, 54)))),
    # таблиця: біла сітка, бірюзовий рядок заголовка, одна зелена клітинка
    "intertab": (f'<rect x="46" y="60" width="164" height="140" rx="14" fill="{W}"/>'
                 f'<path d="M46 74a14 14 0 0 1 14-14h136a14 14 0 0 1 14 14v18H46z" fill="{TEAL}"/>'
                 + "".join(f'<rect x="{56 + c * 39}" y="{102 + r * 24}" width="31" height="16" rx="3" fill="{GREEN if (r, c) == (1, 2) else LIL}"/>'
                           for r in range(4) for c in range(4))),
    # презентація: екран на ніжці, бірюзові стовпчики й зелена лінія
    "interslide": (f'<rect x="40" y="50" width="176" height="122" rx="12" fill="{W}"/>'
                   f'<rect x="40" y="50" width="176" height="18" rx="9" fill="{LIL}"/>'
                   + "".join(f'<rect x="{70 + i * 30}" y="{150 - h}" width="20" height="{h}" rx="4" fill="{TEAL}"/>'
                             for i, h in enumerate((30, 52, 40, 68)))
                   + f'<path d="M66 118l30-16 30 10 30-26 30 6" fill="none" stroke="{GREEN}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
                   f'<rect x="122" y="172" width="12" height="28" fill="{W}"/><rect x="92" y="198" width="72" height="12" rx="6" fill="{W}"/>'),
    # база даних: три білі «диски», бірюзовий верх, зелена мітка запису
    "interdata": ("".join(f'<path d="M58 {y}c0-13 31-22 70-22s70 9 70 22v30c0 13-31 22-70 22s-70-9-70-22z" fill="{W}"/>'
                          f'<path d="M58 {y + 30}c0 13 31 22 70 22s70-9 70-22" fill="none" stroke="{LIL}" stroke-width="5"/>'
                          for y in (148, 104, 60))
                  + f'<ellipse cx="128" cy="60" rx="70" ry="22" fill="{TEAL}"/>'
                  f'<rect x="150" y="122" width="34" height="12" rx="6" fill="{GREEN}"/>'
                  f'<rect x="150" y="166" width="22" height="12" rx="6" fill="{LIL}"/>'),
    # Офіс ШКОЛА: три аркуші віялом — документ, таблиця, слайд
    "ofis": (f'<g transform="rotate(-14 128 150)"><rect x="66" y="58" width="96" height="124" rx="10" fill="#e3e5f5"/>'
             + "".join(f'<rect x="{76 + c * 26}" y="{78 + r * 20}" width="20" height="12" rx="2" fill="{LIL}"/>' for r in range(4) for c in range(3))
             + '</g>'
             f'<g transform="rotate(12 128 150)"><rect x="98" y="58" width="104" height="124" rx="10" fill="#eef0fa"/>'
             f'<rect x="110" y="76" width="80" height="54" rx="6" fill="{LIL}"/>'
             f'<rect x="120" y="104" width="12" height="18" rx="2" fill="{GREEN}"/><rect x="140" y="94" width="12" height="28" rx="2" fill="{GREEN}"/>'
             f'<rect x="160" y="86" width="12" height="36" rx="2" fill="{GREEN}"/></g>'
             f'<rect x="78" y="70" width="100" height="134" rx="12" fill="{W}"/>'
             f'<rect x="92" y="90" width="56" height="12" rx="6" fill="{TEAL}"/>'
             + "".join(f'<rect x="92" y="{y}" width="{w}" height="9" rx="4.5" fill="{LIL}"/>' for y, w in ((116, 72), (134, 72), (152, 72), (170, 46)))),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in ICONS.items():
        (OUT / f"{name}.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">{BG}{body}</svg>',
                                         encoding="utf-8")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        QGuiApplication.instance() or QGuiApplication([])
        for name in ICONS:
            img = QImage(256, 256, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            QSvgRenderer(str(OUT / f"{name}.svg")).render(p)
            p.end()
            img.save(str(OUT / f"{name}.png"))
    except ImportError:
        pass
    print(len(ICONS), "іконок ->", OUT)


if __name__ == "__main__":
    main()
