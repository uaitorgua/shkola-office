"""InterData: ядро бази (без Qt). Файл .idata — звичайна SQLite; службові таблиці _id_*.
Кожна таблиця користувача має прихований ключ id. Поле-посилання зберігає id запису іншої таблиці,
а показує його «підпис» (перше текстове поле) — тому перейменування в одній таблиці одразу видно в усіх зв'язаних."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

TYPES = {"text": "Текст", "number": "Число", "integer": "Ціле число", "date": "Дата", "bool": "Так/ні",
         "choice": "Список", "phone": "Телефон", "email": "E-mail", "link": "Посилання на таблицю", "formula": "Формула"}
SQLT = {"text": "TEXT", "number": "REAL", "integer": "INTEGER", "date": "TEXT", "bool": "INTEGER", "choice": "TEXT",
        "phone": "TEXT", "email": "TEXT", "link": "INTEGER"}
_NAME = re.compile(r"^[^\W\d][\w '’ʼ\-]{0,62}$", re.UNICODE)
_DATE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[\d\s()\-]{7,18}$")
YES, NO = {"так", "true", "1", "+", "yes", "да"}, {"ні", "false", "0", "-", "no", "нет", ""}


class DataError(ValueError):
    """Помилка з поясненням людською мовою (показується вчителю/учню як є)."""


class HasDependents(DataError):
    def __init__(self, msg: str, deps: dict[str, int]):
        super().__init__(msg)
        self.deps = deps


@dataclass
class Field:
    name: str
    type: str = "text"
    required: bool = False
    unique: bool = False
    choices: list[str] = field(default_factory=list)
    link: str = ""            # таблиця, на яку посилається
    formula: str = ""         # для type=formula: вираз SQL над полями «[Поле]»
    hint: str = ""


def q(name: str) -> str:
    """Безпечне ім'я для SQL (лапки)."""
    return '"' + name.replace('"', '""') + '"'


def check_name(name: str, what: str = "Назва") -> str:
    name = (name or "").strip()
    if not _NAME.match(name) or name.lower().startswith("_id_") or name.lower() == "id":
        raise DataError(f"{what} «{name}» не підходить: літери, цифри, пробіл, апостроф, дефіс; починати з літери; без крапки, до 63 символів.")
    return name


# ---------- перетворення значень ----------
def to_date(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    m = _DATE.match(s)
    if m:
        d, mo, y = map(int, m.groups())
        return date(y, mo, d).isoformat()
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        raise DataError(f"«{s}» — не дата. Пишіть як 01.09.2026.") from None


def coerce(f: Field, v, db: "Database | None" = None):
    """Значення з форми/імпорту → значення для SQLite. Помилки — з поясненням."""
    if isinstance(v, str):
        v = v.strip()
    if v in (None, ""):
        if f.required:
            raise DataError(f"Поле «{f.name}» обов'язкове.")
        return None
    t = f.type
    try:
        if t == "number":
            return float(str(v).replace(",", ".").replace(" ", "").replace(" ", ""))
        if t == "integer":
            x = float(str(v).replace(",", ".").replace(" ", ""))
            if x != int(x):
                raise ValueError
            return int(x)
    except ValueError:
        raise DataError(f"У полі «{f.name}» має бути {'ціле ' if t == 'integer' else ''}число, а не «{v}».") from None
    if t == "date":
        return to_date(v)
    if t == "bool":
        s = str(v).strip().lower()
        if s in YES or v is True:
            return 1
        if s in NO or v is False:
            return 0
        raise DataError(f"У полі «{f.name}» — «так» або «ні», а не «{v}».")
    if t == "choice" and f.choices and str(v) not in f.choices:
        raise DataError(f"У полі «{f.name}» можна лише: {', '.join(f.choices)}.")
    if t == "email" and not _EMAIL.match(str(v)):
        raise DataError(f"«{v}» не схоже на e-mail.")
    if t == "phone" and not _PHONE.match(str(v)):
        raise DataError(f"«{v}» не схоже на номер телефону.")
    if t == "link":
        if isinstance(v, int):
            return v
        if db is None:
            raise DataError("Немає бази для пошуку зв'язаного запису.")
        rid = db.find_by_label(f.link, str(v))
        if rid is None:
            raise DataError(f"У таблиці «{f.link}» немає запису «{v}».")
        return rid
    return str(v)


def infer_type(values: list) -> tuple[str, list[str], str]:
    """Автотип стовпця: (тип, варіанти списку, пояснення)."""
    vals = [str(v).strip() for v in values if v not in (None, "") and str(v).strip()]
    if not vals:
        return "text", [], "порожній стовпець — текст"

    def all_(fn):
        try:
            return all(fn(x) for x in vals)
        except (ValueError, DataError):
            return False
    if all_(lambda x: x.lower() in YES | NO - {""}) and len({x.lower() for x in vals}) <= 2:
        return "bool", [], "лише так/ні"
    num = lambda x: float(x.replace(",", ".").replace(" ", ""))
    phone = lambda x: bool(_PHONE.match(x)) and len(re.sub(r"\D", "", x)) >= 9 and (x.startswith(("+", "0", "(")) or " " in x)
    if all_(phone):
        return "phone", [], "телефони"
    if all_(lambda x: num(x) == int(num(x)) and not (len(x) > 1 and x.startswith("0"))):
        return "integer", [], "цілі числа"
    if all_(lambda x: num(x) is not None):
        return "number", [], "числа"
    if all_(lambda x: to_date(x) is not None):
        return "date", [], "дати"
    if all_(lambda x: bool(_EMAIL.match(x))):
        return "email", [], "адреси e-mail"
    uniq = sorted(set(vals))
    if len(vals) >= 6 and len(uniq) <= max(2, min(15, len(vals) // 3)):
        return "choice", uniq, f"список із {len(uniq)} значень, що повторюються"
    return "text", [], "текст"


# ---------- база ----------
class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS _id_meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS _id_fields(tbl TEXT, name TEXT, ord INTEGER, spec TEXT, PRIMARY KEY(tbl, name));
            CREATE TABLE IF NOT EXISTS _id_history(n INTEGER PRIMARY KEY, ts REAL, tbl TEXT, rid INTEGER, action TEXT,
                                                   before TEXT, after TEXT, batch INTEGER);
            CREATE TABLE IF NOT EXISTS _id_objects(kind TEXT, name TEXT, spec TEXT, PRIMARY KEY(kind, name));
        """)
        self.con.execute("INSERT OR IGNORE INTO _id_meta VALUES('format', 'idata-1')")
        self.con.commit()
        self._batch = 0

    def close(self) -> None:
        self.con.close()

    # ---------- схема ----------
    def tables(self) -> list[str]:
        return [r[0] for r in self.con.execute("SELECT DISTINCT tbl FROM _id_fields ORDER BY rowid")]

    def fields(self, tbl: str) -> list[Field]:
        return [Field(**json.loads(r[0])) for r in
                self.con.execute("SELECT spec FROM _id_fields WHERE tbl=? ORDER BY ord", (tbl,))]

    def field(self, tbl: str, name: str) -> Field:
        for f in self.fields(tbl):
            if f.name == name:
                return f
        raise DataError(f"У таблиці «{tbl}» немає поля «{name}».")

    def label_field(self, tbl: str) -> str | None:
        fs = self.fields(tbl)
        return next((f.name for f in fs if f.type in ("text", "choice")), fs[0].name if fs else None)

    def _col(self, f: Field) -> str:
        s = f"{q(f.name)} {SQLT[f.type]}"
        if f.unique:
            s += " UNIQUE"
        if f.type == "link":
            s += f" REFERENCES {q(f.link)}(id)"
        return s

    def create_table(self, name: str, fields: list[Field]) -> None:
        name = check_name(name, "Назва таблиці")
        if name in self.tables():
            raise DataError(f"Таблиця «{name}» уже є.")
        seen = set()
        for f in fields:
            check_name(f.name, "Назва поля")
            if f.name.lower() in seen:
                raise DataError(f"Поле «{f.name}» повторюється.")
            seen.add(f.name.lower())
            if f.type not in TYPES:
                raise DataError(f"Невідомий тип «{f.type}».")
            if f.type == "link" and f.link not in self.tables():
                raise DataError(f"Немає таблиці «{f.link}» для зв'язку.")
        cols = ", ".join(["id INTEGER PRIMARY KEY"] + [self._col(f) for f in fields if f.type != "formula"])
        with self.con:
            self.con.execute(f"CREATE TABLE {q(name)} ({cols})")
            for i, f in enumerate(fields):
                self.con.execute("INSERT INTO _id_fields VALUES(?,?,?,?)", (name, f.name, i, json.dumps(asdict(f), ensure_ascii=False)))
        self._refresh_view(name)

    def add_field(self, tbl: str, f: Field) -> None:
        check_name(f.name, "Назва поля")
        if any(x.name.lower() == f.name.lower() for x in self.fields(tbl)):
            raise DataError(f"Поле «{f.name}» уже є.")
        with self.con:
            if f.type != "formula":
                col = self._col(Field(f.name, f.type, link=f.link))       # UNIQUE не можна через ALTER — перевіряємо самі
                self.con.execute(f"ALTER TABLE {q(tbl)} ADD COLUMN {col}")
            n = len(self.fields(tbl))
            self.con.execute("INSERT INTO _id_fields VALUES(?,?,?,?)", (tbl, f.name, n, json.dumps(asdict(f), ensure_ascii=False)))
        self._refresh_view(tbl)

    def change_type(self, tbl: str, name: str, new_type: str, dry_run: bool = False, choices: list[str] | None = None):
        """Зміна типу з перевіркою: повертає список (id, значення), що не підходять; dry_run — лише перевірити."""
        f = self.field(tbl, name)
        nf = Field(**{**asdict(f), "type": new_type, "choices": choices if choices is not None else f.choices})
        bad, conv = [], []
        for r in self.con.execute(f"SELECT id, {q(name)} FROM {q(tbl)}"):
            try:
                conv.append((coerce(Field(nf.name, nf.type, choices=nf.choices, link=nf.link), r[1], self), r[0]))
            except DataError:
                bad.append((r[0], r[1]))
        if dry_run or bad:
            return bad
        cols = [x for x in self.fields(tbl) if x.type != "formula"]
        self.con.commit()
        self.con.execute("PRAGMA foreign_keys = OFF")          # перебудова таблиці, на яку можуть посилатися інші
        self.con.execute("PRAGMA legacy_alter_table = ON")
        try:
            self._rebuild(tbl, name, nf, cols, conv)
        finally:
            self.con.execute("PRAGMA legacy_alter_table = OFF")
            self.con.execute("PRAGMA foreign_keys = ON")
        for t in self.tables():
            self._refresh_view(t)
        return []

    def _rebuild(self, tbl, name, nf, cols, conv) -> None:
        with self.con:
            tmp = f"_id_tmp_{int(time.time() * 1000)}"
            defs = ", ".join(["id INTEGER PRIMARY KEY"] + [self._col(nf if x.name == name else x) for x in cols])
            for t in self.tables():
                self.con.execute(f"DROP VIEW IF EXISTS {q('_id_v_' + t)}")
            self.con.execute(f"CREATE TABLE {q(tmp)} ({defs})")
            names = ", ".join(["id"] + [q(x.name) for x in cols])
            self.con.execute(f"INSERT INTO {q(tmp)} ({names}) SELECT {names} FROM {q(tbl)}")
            self.con.executemany(f"UPDATE {q(tmp)} SET {q(name)}=? WHERE id=?", conv)
            self.con.execute(f"DROP TABLE {q(tbl)}")
            self.con.execute(f"ALTER TABLE {q(tmp)} RENAME TO {q(tbl)}")
            self.con.execute("UPDATE _id_fields SET spec=? WHERE tbl=? AND name=?",
                             (json.dumps(asdict(nf), ensure_ascii=False), tbl, name))

    def links_to(self, tbl: str) -> list[tuple[str, str]]:
        """Хто посилається на таблицю: [(таблиця, поле)]."""
        return [(t, f.name) for t in self.tables() for f in self.fields(t) if f.type == "link" and f.link == tbl]

    def _refresh_view(self, tbl: str) -> None:
        """Подання _id_v_<таблиця>: підписи замість id у посиланнях і обчислювані поля."""
        parts = [f"t.id AS id"]
        joins = []
        for i, f in enumerate(self.fields(tbl)):
            if f.type == "link":
                lab = self.label_field(f.link) or "id"
                joins.append(f"LEFT JOIN {q(f.link)} j{i} ON j{i}.id = t.{q(f.name)}")
                parts.append(f"j{i}.{q(lab)} AS {q(f.name)}")
            elif f.type == "formula":
                parts.append(f"({self._formula_sql(tbl, f.formula)}) AS {q(f.name)}")
            else:
                parts.append(f"t.{q(f.name)} AS {q(f.name)}")
        with self.con:
            self.con.execute(f"DROP VIEW IF EXISTS {q('_id_v_' + tbl)}")
            self.con.execute(f"CREATE VIEW {q('_id_v_' + tbl)} AS SELECT {', '.join(parts)} FROM {q(tbl)} t {' '.join(joins)}")

    def _formula_sql(self, tbl: str, expr: str) -> str:
        """«=[Бал1]+[Бал2]», «ЯКЩО([Бал]>=10;"так";"ні")» → SQL. Лише поля таблиці й прості функції."""
        names = {f.name for f in self.fields(tbl) if f.type != "formula"}
        s = expr.lstrip("=")

        def fld(m):
            n = m.group(1)
            if n not in names:
                raise DataError(f"У формулі невідоме поле «{n}».")
            return "t." + q(n)
        s = re.sub(r"\[([^\]]+)\]", fld, s)
        for ua, en in (("ЯКЩО", "IIF"), ("ОКРУГЛ", "ROUND"), ("ДОВЖИНА", "LENGTH"), ("ВЕРХНІЙ", "UPPER"),
                       ("АБС", "ABS"), ("МІН", "MIN"), ("МАКС", "MAX")):
            s = re.sub(rf"\b{ua}\s*\(", en + "(", s, flags=re.IGNORECASE)
        s = s.replace(";", ",").replace("&", "||")
        if re.search(r"\b(select|insert|update|delete|drop|attach|pragma)\b", s, re.IGNORECASE):
            raise DataError("У формулі можна лише поля, числа, текст і функції.")
        return s

    # ---------- записи ----------
    def find_by_label(self, tbl: str, label: str) -> int | None:
        lab = self.label_field(tbl)
        r = self.con.execute(f"SELECT id FROM {q(tbl)} WHERE {q(lab)}=? LIMIT 1", (label,)).fetchone()
        return r[0] if r else None

    def rows(self, tbl: str, raw: bool = False) -> list[dict]:
        src = q(tbl) if raw else q("_id_v_" + tbl)
        return [dict(r) for r in self.con.execute(f"SELECT * FROM {src} ORDER BY id")]

    def get(self, tbl: str, rid: int) -> dict:
        r = self.con.execute(f"SELECT * FROM {q(tbl)} WHERE id=?", (rid,)).fetchone()
        if not r:
            raise DataError(f"Запис {rid} у «{tbl}» не знайдено.")
        return dict(r)

    def _check_unique(self, tbl: str, data: dict, rid: int | None) -> None:
        for f in self.fields(tbl):
            if f.unique and data.get(f.name) is not None:
                r = self.con.execute(f"SELECT id FROM {q(tbl)} WHERE {q(f.name)}=? AND id IS NOT ?", (data[f.name], rid)).fetchone()
                if r:
                    raise DataError(f"«{data[f.name]}» у полі «{f.name}» уже є (запис {r[0]}), а значення мають бути різні.")

    def _log(self, tbl, rid, action, before, after) -> None:
        self.con.execute("INSERT INTO _id_history(ts, tbl, rid, action, before, after, batch) VALUES(?,?,?,?,?,?,?)",
                         (time.time(), tbl, rid, action, json.dumps(before, ensure_ascii=False, default=str) if before else None,
                          json.dumps(after, ensure_ascii=False, default=str) if after else None, self._batch))

    def _clean(self, tbl: str, values: dict, partial: bool) -> dict:
        fs = {f.name: f for f in self.fields(tbl) if f.type != "formula"}
        for k in values:
            if k not in fs:
                raise DataError(f"У таблиці «{tbl}» немає поля «{k}».")
        names = values.keys() if partial else fs.keys()
        return {k: coerce(fs[k], values.get(k), self) for k in names}

    def insert(self, tbl: str, values: dict) -> int:
        data = self._clean(tbl, values, partial=False)
        self._check_unique(tbl, data, None)
        with self.con:
            cur = self.con.execute(f"INSERT INTO {q(tbl)} ({', '.join(map(q, data))}) VALUES ({', '.join('?' * len(data))})",
                                   list(data.values())) if data else self.con.execute(f"INSERT INTO {q(tbl)} DEFAULT VALUES")
            self._log(tbl, cur.lastrowid, "insert", None, data)
        return cur.lastrowid

    def update(self, tbl: str, rid: int, values: dict) -> None:
        before = self.get(tbl, rid)
        data = self._clean(tbl, values, partial=True)
        self._check_unique(tbl, data, rid)
        with self.con:
            self.con.execute(f"UPDATE {q(tbl)} SET {', '.join(q(k) + '=?' for k in data)} WHERE id=?", [*data.values(), rid])
            self._log(tbl, rid, "update", {k: before[k] for k in data}, data)

    def dependents(self, tbl: str, rid: int) -> dict[str, int]:
        out = {}
        for t, f in self.links_to(tbl):
            n = self.con.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE {q(f)}=?", (rid,)).fetchone()[0]
            if n:
                out[f"{t}.{f}"] = n
        return out

    def delete(self, tbl: str, rid: int, mode: str = "ask") -> None:
        """mode: ask — помилка з поясненням, якщо є зв'язані; clear — очистити посилання; cascade — видалити й їх."""
        deps = self.dependents(tbl, rid)
        if deps and mode == "ask":
            lab = self.label_field(tbl)
            name = self.get(tbl, rid).get(lab, rid)
            what = "; ".join(f"{k.split('.')[0]}: {n}" for k, n in deps.items())
            raise HasDependents(f"«{name}» використовується ({what}). Очистити ці посилання, видалити разом чи скасувати?", deps)
        self._batch = int(time.time() * 1000)
        try:
            with self.con:
                for key in deps:
                    t, f = key.split(".", 1)
                    for r in self.con.execute(f"SELECT * FROM {q(t)} WHERE {q(f)}=?", (rid,)).fetchall():
                        r = dict(r)
                        if mode == "cascade":
                            self._delete_one(t, r)
                        else:
                            self.con.execute(f"UPDATE {q(t)} SET {q(f)}=NULL WHERE id=?", (r["id"],))
                            self._log(t, r["id"], "update", {f: rid}, {f: None})
                self._delete_one(tbl, self.get(tbl, rid))
        finally:
            self._batch = 0

    def _delete_one(self, tbl: str, row: dict) -> None:
        self.con.execute(f"DELETE FROM {q(tbl)} WHERE id=?", (row["id"],))
        self._log(tbl, row["id"], "delete", row, None)

    def history(self, tbl: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM _id_history" + (" WHERE tbl=?" if tbl else "") + " ORDER BY n DESC LIMIT ?"
        return [dict(r) for r in self.con.execute(sql, ((tbl, limit) if tbl else (limit,)))]

    def undo(self) -> str:
        """Повернути як було останню дію (разом з її каскадом)."""
        last = self.con.execute("SELECT * FROM _id_history ORDER BY n DESC LIMIT 1").fetchone()
        if not last:
            raise DataError("Немає що повертати.")
        batch = last["batch"]
        items = (self.con.execute("SELECT * FROM _id_history WHERE batch=? ORDER BY n DESC", (batch,)).fetchall()
                 if batch else [last])
        with self.con:
            for h in items:
                t, rid = h["tbl"], h["rid"]
                b = json.loads(h["before"]) if h["before"] else None
                if h["action"] == "insert":
                    self.con.execute(f"DELETE FROM {q(t)} WHERE id=?", (rid,))
                elif h["action"] == "update":
                    self.con.execute(f"UPDATE {q(t)} SET {', '.join(q(k) + '=?' for k in b)} WHERE id=?", [*b.values(), rid])
                else:
                    self.con.execute(f"INSERT INTO {q(t)} ({', '.join(map(q, b))}) VALUES ({', '.join('?' * len(b))})",
                                     list(b.values()))
                self.con.execute("DELETE FROM _id_history WHERE n=?", (h["n"],))
        return f"Повернуто: {last['action']} у «{last['tbl']}»"

    # ---------- імпорт / експорт ----------
    def import_rows(self, name: str, header: list[str], rows: list[list]) -> list[tuple[str, str, str]]:
        """Нова таблиця з автотипами. Повертає [(поле, тип, пояснення)]."""
        header = [re.sub(r"[^\w '’ʼ\-]", " ", h or f"Поле {i + 1}").strip() or f"Поле {i + 1}" for i, h in enumerate(header)]
        header = [h if not h[0].isdigit() else "П " + h for h in header]
        if "id" in [h.lower() for h in header]:
            header = [("Код" if h.lower() == "id" else h) for h in header]
        report, fields = [], []
        for i, h in enumerate(header):
            t, ch, why = infer_type([r[i] if i < len(r) else None for r in rows])
            fields.append(Field(h, t, choices=ch))
            report.append((h, TYPES[t], why))
        self.create_table(name, fields)
        self._batch = int(time.time() * 1000)
        try:
            for r in rows:
                self.insert(name, {h: (r[i] if i < len(r) else None) for i, h in enumerate(header)})
        finally:
            self._batch = 0
        return report

    def import_csv(self, path: Path, name: str | None = None):
        raw = Path(path).read_bytes()
        text = next((raw.decode(e) for e in ("utf-8-sig", "cp1251") if _decodes(raw, e)), raw.decode("utf-8", "replace"))
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t") if text.strip() else csv.excel
        data = [r for r in csv.reader(text.splitlines(), dialect) if any(c.strip() for c in r)]
        return self.import_rows(name or Path(path).stem, data[0], data[1:])

    def import_xlsx(self, path: Path) -> dict[str, list]:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True, read_only=True)
        out = {}
        for ws in wb.worksheets:
            data = [[("" if c is None else c) for c in r] for r in ws.iter_rows(values_only=True)]
            data = [r for r in data if any(str(c).strip() for c in r)]
            if len(data) >= 1:
                out[ws.title] = self.import_rows(ws.title, [str(c) for c in data[0]], data[1:])
        return out

    def export_csv(self, tbl_or_rows, path: Path) -> None:
        rows = self.rows(tbl_or_rows) if isinstance(tbl_or_rows, str) else tbl_or_rows
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            if rows:
                keys = [k for k in rows[0] if k != "id"]
                w.writerow(keys)
                w.writerows([[r[k] for k in keys] for r in rows])

    def export_xlsx(self, path: Path, tables: list[str] | None = None) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook()
        wb.remove(wb.active)
        for t in tables or self.tables():
            ws = wb.create_sheet(t[:31])
            rows = self.rows(t)
            keys = [f.name for f in self.fields(t)]
            ws.append(keys)
            for c in ws[1]:
                c.font, c.fill = Font(bold=True), PatternFill("solid", start_color="E3F1EC")
            for r in rows:
                ws.append([r.get(k) for k in keys])
            ws.freeze_panes = "A2"
        wb.save(path)

    def export_sql(self, path: Path) -> None:
        Path(path).write_text("\n".join(self.con.iterdump()), encoding="utf-8")

    @classmethod
    def open_sqlite(cls, src: Path, dst: Path) -> "Database":
        """Відкрити чужу SQLite (.db/.sqlite): копія в .idata з описом полів за типами SQLite."""
        import shutil
        shutil.copyfile(src, dst)
        db = cls(dst)
        known = set(db.tables())
        for (t,) in db.con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_id_%' "
                                   "AND name NOT LIKE 'sqlite_%'").fetchall():
            if t in known:
                continue
            cols = db.con.execute(f"PRAGMA table_info({q(t)})").fetchall()
            if not any(c["name"] == "id" and c["pk"] for c in cols):
                continue                       # без ключа id — лише для читання через SQL
            m = {"INTEGER": "integer", "REAL": "number", "NUMERIC": "number"}
            for i, c in enumerate([c for c in cols if c["name"] != "id"]):
                f = Field(c["name"], m.get((c["type"] or "").upper(), "text"))
                db.con.execute("INSERT INTO _id_fields VALUES(?,?,?,?)", (t, f.name, i, json.dumps(asdict(f), ensure_ascii=False)))
            db.con.commit()
            db._refresh_view(t)
        return db

    # ---------- збережені об'єкти: запити, форми, звіти ----------
    def save_object(self, kind: str, name: str, spec: dict) -> None:
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO _id_objects VALUES(?,?,?)", (kind, name, json.dumps(spec, ensure_ascii=False)))

    def objects(self, kind: str) -> dict[str, dict]:
        return {r[0]: json.loads(r[1]) for r in self.con.execute("SELECT name, spec FROM _id_objects WHERE kind=? ORDER BY name", (kind,))}

    def delete_object(self, kind: str, name: str) -> None:
        with self.con:
            self.con.execute("DELETE FROM _id_objects WHERE kind=? AND name=?", (kind, name))


def _decodes(b: bytes, enc: str) -> bool:
    try:
        b.decode(enc)
        return True
    except UnicodeDecodeError:
        return False
