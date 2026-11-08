"""Налаштування від застосунку-господаря (Сканер ШКОЛА, Накази ШКОЛА, …).
Застосунок викликає shkola_office.configure(...) ДО імпорту редакторів: модулі читають значення під час імпорту."""

import os
import sys
from pathlib import Path

APP_NAME = "Офіс ШКОЛА"
APP_ID = "ofis-shkola"
INTERTEXT = "InterText"
INTERTAB = "InterTab"
_base = getattr(sys, "_MEIPASS", None)
OFFICE_ASSETS = (Path(_base) / "shkola_office_assets") if _base else Path(__file__).resolve().parent / "assets"
ASSETS = OFFICE_ASSETS                      # ресурси застосунку (логотип); господар підміняє
LOGO_SVG = ASSETS / "logo.svg"
LOGO_PNG = ASSETS / "logo.png"
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_ID
