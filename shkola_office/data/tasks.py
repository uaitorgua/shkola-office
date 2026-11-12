"""InterData: навчальний шар.
1) explain_sql(history_item) — що сталося в SQL після дії в таблиці/формі (для «пояснення кроку»).
2) Завдання з автоперевіркою: файл .itask (zip: base.idata + task.json). Учитель зберігає базу й еталонний запит
   з умовою; учень відкриває, складає запит (конструктор або SQL), програма звіряє результат з еталоном. Без сервера."""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .db import Database, DataError, q
from .query import Query, run_sql


def explain_sql(h: dict) -> str:
    t, rid = h["tbl"], h["rid"]
    b = json.loads(h["before"]) if h.get("before") else {}
    a = json.loads(h["after"]) if h.get("after") else {}
    lit = lambda v: "NULL" if v is None else (str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'")
    if h["action"] == "insert":
        return f"INSERT INTO {q(t)} ({', '.join(map(q, a))}) VALUES ({', '.join(lit(v) for v in a.values())});"
    if h["action"] == "update":
        return f"UPDATE {q(t)} SET {', '.join(f'{q(k)} = {lit(v)}' for k, v in a.items())} WHERE id = {rid};"
    return f"DELETE FROM {q(t)} WHERE id = {rid};"


def _result(db: Database, spec_or_sql) -> tuple[list[str], list[tuple]]:
    return run_sql(db, spec_or_sql) if isinstance(spec_or_sql, str) else Query(db, spec_or_sql).run()


def save_task(db: Database, path: Path, title: str, condition: str, answer, ordered: bool = False) -> None:
    """answer — словник конструктора або SQL-рядок (еталон учителя)."""
    _result(db, answer)                                     # еталон має виконуватися
    db.con.commit()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(db.path, "base.idata")
        z.writestr("task.json", json.dumps({"format": "itask-1", "title": title, "condition": condition,
                                            "answer": answer, "ordered": ordered}, ensure_ascii=False))


def open_task(path: Path, workdir: Path | None = None) -> tuple[Database, dict]:
    """Розпакувати завдання: учень працює з копією бази; еталон лишається в task (учню не показується)."""
    workdir = Path(workdir or tempfile.mkdtemp(prefix="itask_"))
    with zipfile.ZipFile(path) as z:
        z.extract("base.idata", workdir)
        task = json.loads(z.read("task.json").decode("utf-8"))
    dst = workdir / (Path(path).stem + ".idata")
    shutil.move(str(workdir / "base.idata"), dst)
    return Database(dst), task


def check(db: Database, task: dict, student) -> tuple[bool, str]:
    """Звірити результат учня з еталоном. Повертає (правильно?, пояснення людською мовою)."""
    try:
        sc, sr = _result(db, student)
    except DataError as e:
        return False, f"Запит не виконався: {e}"
    ec, er = _result(db, task["answer"])
    norm = lambda rows: [tuple("" if v is None else (round(v, 2) if isinstance(v, float) else v) for v in r) for r in rows]
    sr, er = norm(sr), norm(er)
    if len(sc) != len(ec):
        return False, f"Стовпців {len(sc)}, а потрібно {len(ec)}."
    if len(sr) != len(er):
        return False, f"Рядків {len(sr)}, а потрібно {len(er)}. Перевірте умови відбору."
    same = sr == er if task.get("ordered") else sorted(map(str, sr)) == sorted(map(str, er))
    if not same:
        return False, "Кількість рядків правильна, але значення відрізняються." + \
            (" Можливо, порядок сортування." if task.get("ordered") and sorted(map(str, sr)) == sorted(map(str, er)) else "")
    return True, "Правильно! Результат збігається з еталоном."
