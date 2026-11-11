"""InterData: запити (конструктор → SQL → речення українською), форми й звіти. Без Qt.
Запит — словник:
  {"table": "Учні", "fields": [{"name": "Прізвище"}, {"name": "Клас.Керівник"}, {"name": "Бал", "agg": "avg"}],
   "where": [{"field": "Бал", "op": "≥", "value": "10"}], "group": ["Клас"], "order": [{"field": "Бал", "desc": true}],
   "limit": 0}
«Поле.ПолеЗв'язаної» — поле з таблиці, на яку посилається «Поле» (зв'язок підставляється сам)."""
from __future__ import annotations

import html
import re

from .db import Database, DataError, q

AGG = {"": "", "count": "Кількість", "sum": "Сума", "avg": "Середнє", "min": "Найменше", "max": "Найбільше"}
OPS = ["=", "≠", ">", "<", "≥", "≤", "містить", "починається з", "порожнє", "не порожнє"]
_SQLOP = {"=": "=", "≠": "<>", ">": ">", "<": "<", "≥": ">=", "≤": "<="}


class Query:
    def __init__(self, db: Database, spec: dict) -> None:
        self.db, self.spec = db, spec
        self.params: list = []

    def _col(self, name: str, joins: dict) -> tuple[str, "object"]:
        """Ім'я поля (або шлях Поле.Поле) → вираз SQL і опис поля."""
        tbl = self.spec["table"]
        if "." in name:
            link, sub = name.split(".", 1)
            lf = self.db.field(tbl, link)
            if lf.type != "link":
                raise DataError(f"«{link}» — не посилання, тому «{name}» не можна.")
            al = joins.setdefault(link, f"j{len(joins)}")
            sf = self.db.field(lf.link, sub)
            return f"{al}.{q(sub)}", sf
        if name == "id":
            return "t.id", None
        f = self.db.field(tbl, name)
        return f"t.{q(name)}", f

    def sql(self) -> str:
        s = self.spec
        if not s.get("table"):
            raise DataError("Оберіть таблицю.")
        self.params = []
        joins: dict[str, str] = {}
        sel = []
        for c in s.get("fields") or [{"name": f.name} for f in self.db.fields(s["table"])]:
            expr, _ = self._col(c["name"], joins)
            agg = c.get("agg", "")
            title = c.get("as") or (f"{AGG[agg]} {c['name']}" if agg else c["name"])
            if agg == "count":
                expr = f"COUNT({expr})"
            elif agg:
                expr = f"ROUND({'AVG' if agg == 'avg' else agg.upper()}({expr}), 2)"
            sel.append(f"{expr} AS {q(title)}")
        where = []
        for w in s.get("where", []):
            expr, f = self._col(w["field"], joins)
            op, v = w["op"], w.get("value", "")
            if op == "порожнє":
                where.append(f"({expr} IS NULL OR {expr} = '')")
                continue
            if op == "не порожнє":
                where.append(f"({expr} IS NOT NULL AND {expr} <> '')")
                continue
            if op == "містить":
                where.append(f"{expr} LIKE ?")
                self.params.append(f"%{v}%")
                continue
            if op == "починається з":
                where.append(f"{expr} LIKE ?")
                self.params.append(f"{v}%")
                continue
            if f is not None and f.type in ("number", "integer"):
                v = float(str(v).replace(",", "."))
            elif f is not None and f.type == "date":
                from .db import to_date
                v = to_date(v)
            elif f is not None and f.type == "bool":
                v = 1 if str(v).lower() in ("так", "1", "true") else 0
            where.append(f"{expr} {_SQLOP[op]} ?")
            self.params.append(v)
        group = [self._col(g, joins)[0] for g in s.get("group", [])]
        order = [f"{q(o['field'])}{' DESC' if o.get('desc') else ''}" for o in s.get("order", [])]
        src = f"{q('_id_v_' + s['table'])} t"
        for link, al in joins.items():
            lf = self.db.field(s["table"], link)
            src += f" LEFT JOIN {q(lf.link)} {al} ON {al}.id = (SELECT {q(link)} FROM {q(s['table'])} WHERE id = t.id)"
        out = f"SELECT {', '.join(sel)}\nFROM {src}"
        if where:
            out += "\nWHERE " + " AND ".join(where)
        if group:
            out += "\nGROUP BY " + ", ".join(group)
        if order:
            out += "\nORDER BY " + ", ".join(order)
        if s.get("limit"):
            out += f"\nLIMIT {int(s['limit'])}"
        return out

    def run(self) -> tuple[list[str], list[tuple]]:
        sql = self.sql()
        cur = self.db.con.execute(sql, self.params)
        return [d[0] for d in cur.description], [tuple(r) for r in cur.fetchall()]

    def words(self) -> str:
        """Запит людською мовою — для учня й для «пояснення кроку»."""
        s = self.spec
        fs = s.get("fields") or []
        what = ", ".join((AGG[c.get("agg", "")].lower() + " " if c.get("agg") else "") + f"«{c['name']}»" for c in fs) or "усі поля"
        t = f"Показати {what} з таблиці «{s.get('table', '?')}»"
        if s.get("where"):
            t += ", де " + " і ".join(f"«{w['field']}» {w['op']}" + (f" {w.get('value')}" if w["op"] not in ("порожнє", "не порожнє") else "")
                                      for w in s["where"])
        if s.get("group"):
            t += ", для кожного значення " + ", ".join(f"«{g}»" for g in s["group"])
        if s.get("order"):
            t += ", впорядкувати за " + ", ".join(f"«{o['field']}»" + (" (від більшого)" if o.get("desc") else "") for o in s["order"])
        if s.get("limit"):
            t += f", лише перші {s['limit']}"
        return t + "."


def run_sql(db: Database, sql: str) -> tuple[list[str], list[tuple]]:
    """SQL, набраний руками: лише читання (пісочниця), службові таблиці приховано."""
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise DataError("Тут — лише запити на читання (SELECT). Змінювати дані — у таблицях або формах.")
    db.con.execute("PRAGMA query_only = ON")
    try:
        cur = db.con.execute(sql)
        return [d[0] for d in cur.description], [tuple(r) for r in cur.fetchall()]
    except Exception as e:  # noqa: BLE001
        raise DataError(f"SQL не виконався: {e}") from None
    finally:
        db.con.execute("PRAGMA query_only = OFF")


# ---------- форми ----------
def auto_form(db: Database, tbl: str) -> dict:
    """Форма одним кліком: усі поля + підтаблиця записів, що посилаються на цей запис."""
    subs = [{"table": t, "field": f} for t, f in db.links_to(tbl)]
    return {"table": tbl, "fields": [f.name for f in db.fields(tbl) if f.type != "formula"],
            "show": [f.name for f in db.fields(tbl) if f.type == "formula"], "subtables": subs,
            "title": tbl}


def sub_rows(db: Database, sub: dict, rid: int) -> tuple[list[str], list[tuple]]:
    cols = [f.name for f in db.fields(sub["table"]) if f.name != sub["field"]]
    sql = (f"SELECT v.id, {', '.join('v.' + q(c) for c in cols)} FROM {q('_id_v_' + sub['table'])} v "
           f"JOIN {q(sub['table'])} r ON r.id = v.id WHERE r.{q(sub['field'])} = ? ORDER BY v.id")
    return ["id", *cols], [tuple(r) for r in db.con.execute(sql, (rid,))]


# ---------- звіти ----------
def report(db: Database, spec: dict) -> dict:
    """spec: {"title", "query": {...} | "table", "group": поле, "totals": {поле: agg}}.
    Повертає {"title", "columns", "groups": [(значення, рядки, підсумки)], "totals"}."""
    qspec = spec.get("query") or {"table": spec["table"]}
    cols, rows = Query(db, qspec).run()
    g = spec.get("group")
    gi = cols.index(g) if g in cols else None
    groups: dict = {}
    for r in rows:
        groups.setdefault(r[gi] if gi is not None else None, []).append(r)

    def tot(rs):
        out = {}
        for c, agg in (spec.get("totals") or {}).items():
            if c not in cols:
                continue
            vals = [r[cols.index(c)] for r in rs if r[cols.index(c)] not in (None, "")]
            nums = [v for v in vals if isinstance(v, (int, float))]
            out[c] = {"count": len(vals), "sum": round(sum(nums), 2), "avg": round(sum(nums) / len(nums), 2) if nums else "",
                      "min": min(nums) if nums else "", "max": max(nums) if nums else ""}[agg]
        return out
    return {"title": spec.get("title") or qspec["table"], "columns": [c for c in cols if c != g],
            "group": g, "groups": [(k, [tuple(v for i, v in enumerate(r) if i != gi) for r in rs], tot(rs))
                                   for k, rs in sorted(groups.items(), key=lambda kv: str(kv[0]))],
            "totals": tot(rows), "count": len(rows), "agg": spec.get("totals") or {}}


def report_html(rep: dict) -> str:
    e = lambda v: html.escape("" if v is None else (f"{v:g}" if isinstance(v, float) else str(v)))
    cols = rep["columns"]
    head = "".join(f"<th>{e(c)}</th>" for c in cols)
    body = []
    for k, rs, tot in rep["groups"]:
        if rep["group"]:
            body.append(f'<tr class="g"><td colspan="{len(cols)}">{e(rep["group"])}: {e(k)} — {len(rs)}</td></tr>')
        body += ["<tr>" + "".join(f"<td>{e(v)}</td>" for v in r) + "</tr>" for r in rs]
        if tot and rep["group"]:
            body.append('<tr class="t">' + "".join(f"<td>{e(tot.get(c, ''))}</td>" for c in cols) + "</tr>")
    if rep["totals"]:
        body.append('<tr class="T">' + "".join(f"<td>{e(rep['totals'].get(c, ''))}</td>" for c in cols) + "</tr>")
    names = {"count": "кількість", "sum": "сума", "avg": "середнє", "min": "найменше", "max": "найбільше"}
    legend = ", ".join(f"{c}: {names[a]}" for c, a in rep["agg"].items())
    return (f"<html><head><meta charset='utf-8'><style>body{{font-family:Segoe UI,Arial;color:#1f2d2a}}"
            f"h1{{color:#135548;font-size:20pt}}table{{border-collapse:collapse;width:100%}}"
            f"th{{background:#e3f1ec;text-align:left}}td,th{{border:1px solid #cfdcd7;padding:4px 6px}}"
            f".g td{{background:#f4f8f6;font-weight:bold}}.t td{{font-style:italic;color:#135548}}"
            f".T td{{font-weight:bold;background:#fff5dc}}</style></head><body><h1>{e(rep['title'])}</h1>"
            f"<p>Записів: {rep['count']}{'. Підсумки — ' + e(legend) if legend else ''}</p>"
            f"<table><tr>{head}</tr>{''.join(body)}</table></body></html>")


def report_xlsx(rep: dict, path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = rep["title"][:31] or "Звіт"
    ws.append([rep["title"]])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(rep["columns"])
    for c in ws[2]:
        c.font, c.fill = Font(bold=True), PatternFill("solid", start_color="E3F1EC")
    for k, rs, tot in rep["groups"]:
        if rep["group"]:
            ws.append([f"{rep['group']}: {k}"])
            ws.cell(ws.max_row, 1).font = Font(bold=True)
        for r in rs:
            ws.append(list(r))
        if tot and rep["group"]:
            ws.append([tot.get(c, "") for c in rep["columns"]])
    if rep["totals"]:
        ws.append([rep["totals"].get(c, "") for c in rep["columns"]])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
    wb.save(path)
