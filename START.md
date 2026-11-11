# START — Офіс ШКОЛА (08.11.2026)

Спільні редактори ГС «УАІТ» для шкільних застосунків: **InterText** (документи), **InterTab** (таблиці), далі **InterSlide** (презентації). Правки редакторів робляться ЛИШЕ тут; застосунки (Сканер ШКОЛА, Накази ШКОЛА) підключають репозиторій як git-підмодуль `vendor/shkola-office` і оновлюють прив'язку свідомо, з прогоном своїх тестів.

## Підключення в застосунку
1. `git submodule add <url> vendor/shkola-office`; шлях `vendor/shkola-office` у `sys.path` до імпортів.
2. До першого імпорту `shkola_office.ui.*`: `shkola_office.configure(APP_NAME=…, APP_ID=…, ASSETS=…, LOGO_SVG=…, LOGO_PNG=…, DATA_DIR=…)`.
3. PyInstaller: `datas += [('vendor/shkola-office/shkola_office/assets', 'shkola_office_assets')]`.

## Стан
- 08.11.2026: винесено зі «Сканер ШКОЛА» (коміт 37adfe1): `ui/` (InterText, InterTab, стрічка, власні SVG-іконки, колонтитули/зміст/шаблони, фільтр/умовне форматування — заготовка), `export/html_docx.py`, `export/xlsx_io.py`, `ocr/formula.py` (лише LaTeX→Unicode). Тести `tests/test_editors.py`, `tests/test_doc_pages.py` — OK (офскрин: `QT_QPA_FONTDIR=C:/Windows/Fonts`).

- 08.11.2026 **Етап 4 InterTab**: фільтр за значеннями стовпця, закріплення верхнього рядка (у XLSX freeze_panes, читається назад), умовне форматування (умова/між/містить, пресет «Оцінки 1–12»; у XLSX — правила Excel), формати «₴» і «дата», функції COUNTIFS, SUMIFS, AVERAGEIFS, MAXIFS, MINIFS, MEDIAN, MODE, RANK, ROUNDUP, ROUNDDOWN, COUNTBLANK; шаблони: журнал оцінок, табель успішності, облік відвідування, розклад уроків (Додати → Шаблон). Тест `tests/test_sheet_extra.py` OK. Увага: десятковий роздільник у формулах — крапка («2,31» = два аргументи).

- 08.11.2026 **Етап 5**: `tests/test_libreoffice.py` — DOCX (текст, таблиця, колонтитул «Сторінка N з M») і XLSX (SUM, ROUND(AVERAGE), COUNTIF, підсвітка, закріплення) через LibreOffice headless → PDF: OK (3 сторінки, формули перераховані). Без LibreOffice тест пропускається.
- 08.11.2026 **Етап 6**: Font Awesome прибрано повністю (лише власні SVG), формулювання «як Word/Excel» у коді й інтерфейсі замінено (фільтр «Документ DOCX»); згадки Excel лишились лише як назва формату файлів.

## Далі
- Підключити в Сканер ШКОЛА (перехідники), потім Накази ШКОЛА — лише на «так» користувача.
- **InterSlide** — редактор презентацій для шкіл (задум 08.11, деталі в `docs/INTERSLIDE.md`).
- **InterData** — навчальна база даних (`shkola_office/data/`, концепція в `docs/INTERDATA.md`), після InterSlide. Пауза: не починати без команди користувача.
- ✔ 11.11 InterSlide етап 1: модель `slide/model.py`, формат .islide (zip+JSON+media), вікно `ui/slide_window.py` (стрічка Слайди/Додати/Формат, мініатюри, нотатки, перетягування й розмір), експорт PPTX і PDF; тест `tests/test_interslide.py`. Далі етап 2: макети й 2 теми. Репозиторій: https://github.com/uaitorgua/shkola-office (публічний, 11.11); Сканер бере підмодуль звідти.
- **Офіс ШКОЛА окремим застосунком для macOS і Linux** (побажання 08.11): той самий код (PySide6 кросплатформний); збірка .app/.dmg на Mac (черга Mac), AppImage/Flatpak для Linux; перевірити шрифти (Times New Roman → Liberation Serif/Tinos), шляхи даних (~/Library, ~/.local/share), друк через CUPS.
- Репозиторій на GitHub (відкритий) — після «так».
