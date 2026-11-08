# START — Офіс ШКОЛА (08.11.2026)

Спільні редактори ГС «УАІТ» для шкільних застосунків: **InterText** (документи), **InterTab** (таблиці), далі **InterSlide** (презентації). Правки редакторів робляться ЛИШЕ тут; застосунки (Сканер ШКОЛА, Накази ШКОЛА) підключають репозиторій як git-підмодуль `vendor/shkola-office` і оновлюють прив'язку свідомо, з прогоном своїх тестів.

## Підключення в застосунку
1. `git submodule add <url> vendor/shkola-office`; шлях `vendor/shkola-office` у `sys.path` до імпортів.
2. До першого імпорту `shkola_office.ui.*`: `shkola_office.configure(APP_NAME=…, APP_ID=…, ASSETS=…, LOGO_SVG=…, LOGO_PNG=…, DATA_DIR=…)`.
3. PyInstaller: `datas += [('vendor/shkola-office/shkola_office/assets', 'shkola_office_assets')]`.

## Стан
- 08.11.2026: винесено зі «Сканер ШКОЛА» (коміт 37adfe1): `ui/` (InterText, InterTab, стрічка, власні SVG-іконки, колонтитули/зміст/шаблони, фільтр/умовне форматування — заготовка), `export/html_docx.py`, `export/xlsx_io.py`, `ocr/formula.py` (лише LaTeX→Unicode). Тести `tests/test_editors.py`, `tests/test_doc_pages.py` — OK (офскрин: `QT_QPA_FONTDIR=C:/Windows/Fonts`).

## Далі
- Підключити в Сканер ШКОЛА (перехідники), потім Накази ШКОЛА — лише на «так» користувача.
- Етап 4: підключити `ui/sheet_extra.py` (фільтр, закріплення, умовне форматування, шаблони журналу/табеля), нові функції й формати.
- Етапи 5–6: перевірка експорту в LibreOffice, прибрати Font Awesome і згадки Word/Excel.
- **InterSlide** — редактор презентацій для шкіл (задум 08.11, деталі в `docs/INTERSLIDE.md`).
- Репозиторій на GitHub (відкритий) — після «так».
