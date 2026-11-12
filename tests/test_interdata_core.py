"""InterData ядро: типи й перевірки, автотипи, зв'язки й каскад, формули, історія/повернення, зміна типу,
запити (конструктор/слова/SQL), форми, звіти, імпорт і експорт."""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shkola_office.data.db import Database, DataError, Field, HasDependents, infer_type  # noqa: E402
from shkola_office.data.query import Query, auto_form, report, report_html, report_xlsx, run_sql, sub_rows  # noqa: E402
from shkola_office.data.samples import build  # noqa: E402

D = Path(tempfile.mkdtemp())

# автотипи
assert infer_type(["1", "2", "12"])[0] == "integer"
assert infer_type(["1,5", "2", "3.25"])[0] == "number"
assert infer_type(["01.09.2026", "15.10.2026"])[0] == "date"
assert infer_type(["так", "ні", "так"])[0] == "bool"
assert infer_type(["+380 67 123 45 67", "067 765 43 21"])[0] == "phone"
assert infer_type(["a@b.ua", "x@y.com"])[0] == "email"
t, ch, why = infer_type(["5-А", "5-Б", "5-А", "5-Б", "5-А", "5-А", "5-Б"])
assert t == "choice" and ch == ["5-А", "5-Б"] and "список" in why

db = Database(D / "school.idata")
build(db, "Шкільна бібліотека")
assert db.tables() == ["Класи", "Читачі", "Книги", "Видачі"]
r = db.rows("Читачі")[0]
assert r["Клас"] in ("5-А", "6-Б", "7-А")                       # підпис замість id

# перевірки людською мовою
for bad, msg in (({"Прізвище": ""}, "обов'язкове"), ({"Прізвище": "А", "Телефон батьків": "abc"}, "телефону"),
                 ({"Прізвище": "А", "Клас": "9-Я"}, "немає запису")):
    try:
        db.insert("Читачі", bad)
        raise AssertionError(bad)
    except DataError as e:
        assert msg in str(e), (msg, e)
try:
    db.insert("Класи", {"Назва": "5-А"})
    raise AssertionError("unique")
except DataError as e:
    assert "уже є" in str(e)

# зміна в одній таблиці видно по зв'язку
k5 = db.find_by_label("Класи", "5-А")
n5 = sum(1 for r in db.rows("Читачі") if r["Клас"] == "5-А")
db.update("Класи", k5, {"Назва": "5-А (новий)"})
assert sum(1 for r in db.rows("Читачі") if r["Клас"] == "5-А (новий)") == n5

# видалення з поясненням і каскадом; повернення
try:
    db.delete("Класи", k5)
    raise AssertionError("deps")
except HasDependents as e:
    assert "Читачі" in str(e) and e.deps
before = len(db.rows("Читачі"))
db.delete("Класи", k5, mode="clear")
assert len(db.rows("Читачі")) == before and all(r["Клас"] != "5-А (новий)" for r in db.rows("Читачі"))
db.undo()
assert sum(1 for r in db.rows("Читачі") if r["Клас"] == "5-А (новий)") == n5, "повернуто разом з каскадом"

# зміна типу з перевіркою
db.add_field("Книги", Field("Ціна"))
db.update("Книги", 1, {"Ціна": "120,50"})
db.update("Книги", 2, {"Ціна": "дорого"})
assert db.change_type("Книги", "Ціна", "number", dry_run=True) == [(2, "дорого")]
db.update("Книги", 2, {"Ціна": ""})
assert db.change_type("Книги", "Ціна", "number") == [] and db.rows("Книги")[0]["Ціна"] == 120.5

# формули
j = Database(D / "journal.idata")
build(j, "Журнал оцінок")
rows = j.rows("Оцінки")
assert all(r["Рівень"] in ("високий", "достатній", "середній", "початковий") for r in rows)
assert all((r["Бал"] >= 10) == (r["Рівень"] == "високий") for r in rows)

# запити
qs = {"table": "Оцінки", "fields": [{"name": "Учень"}, {"name": "Бал", "agg": "avg"}],
      "where": [{"field": "Предмет", "op": "=", "value": "Математика"}], "group": ["Учень"],
      "order": [{"field": "Середнє Бал", "desc": True}]}
qq = Query(j, qs)
cols, res = qq.run()
assert cols == ["Учень", "Середнє Бал"] and res and res[0][1] >= res[-1][1]
assert "де «Предмет» = Математика" in qq.words() and "GROUP BY" in qq.sql()
cols, res = Query(j, {"table": "Оцінки", "fields": [{"name": "Предмет.Вчитель"}, {"name": "Бал"}],
                      "where": [{"field": "Бал", "op": "≥", "value": "10"}]}).run()
assert all(r[1] >= 10 for r in res) and res[0][0].endswith(".")
cols, res = run_sql(j, 'SELECT "Прізвище" FROM "Учні" WHERE "Клас" = \'7-А\'')
assert cols == ["Прізвище"]
try:
    run_sql(j, 'DELETE FROM "Учні"')
    raise AssertionError("sql write")
except DataError:
    pass
assert len(j.rows("Учні")) == 10

# форми
fm = auto_form(j, "Учні")
assert {"table": "Оцінки", "field": "Учень"} in fm["subtables"]
c, rr = sub_rows(j, fm["subtables"][0], 1)
assert "Бал" in c and all(len(x) == len(c) for x in rr)

# звіти
rep = report(j, {"title": "Успішність", "query": {"table": "Оцінки", "fields": [{"name": "Предмет"}, {"name": "Учень"}, {"name": "Бал"}]},
                 "group": "Предмет", "totals": {"Бал": "avg"}})
assert len(rep["groups"]) == 3 and rep["totals"]["Бал"]
h = report_html(rep)
assert "Успішність" in h and "Математика" in h
report_xlsx(rep, D / "rep.xlsx")

# імпорт / експорт
with open(D / "pupils.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["Прізвище", "Дата народження", "Клас", "Пільга", "Телефон"])
    for i in range(8):
        w.writerow([f"Учень{i}", f"0{i + 1}.03.2014", "5-А" if i % 2 else "5-Б", "так" if i % 3 == 0 else "ні", f"067 123 45 6{i}"])
imp = Database(D / "imp.idata")
rep2 = imp.import_csv(D / "pupils.csv", "Учні")
types = {f.name: f.type for f in imp.fields("Учні")}
assert types == {"Прізвище": "text", "Дата народження": "date", "Клас": "choice", "Пільга": "bool", "Телефон": "phone"}, types
j.export_xlsx(D / "j.xlsx")
j.export_csv("Оцінки", D / "o.csv")
j.export_sql(D / "j.sql")
imp2 = Database(D / "imp2.idata")
got = imp2.import_xlsx(D / "j.xlsx")
assert set(got) == {"Учні", "Предмети", "Оцінки"} and len(imp2.rows("Оцінки")) == 40
o = Database.open_sqlite(D / "journal.idata", D / "copy.idata")
assert len(o.rows("Оцінки")) == 40
print("INTERDATA ЯДРО OK", D)

# нормалізація: «Клас» і «Керівник» повторюються разом → окрема таблиця
n = Database(D / "norm.idata")
n.import_rows("Учні", ["Прізвище", "Клас", "Керівник"],
              [[f"У{i}", ["5-А", "5-Б", "6-А"][i % 3], ["Іваненко", "Петренко", "Сидоренко"][i % 3]] for i in range(15)])
h = n.normalize_hints("Учні")
assert h and set(h[0]["cols"]) == {"Клас", "Керівник"} and "разом" in h[0]["why"], h
before = {(r["Прізвище"], r["Клас"]) for r in n.rows("Учні")}
assert n.extract_table("Учні", h[0]["cols"], "Класи") == 3
assert [f.type for f in n.fields("Учні") if f.name == "Клас"] == ["link"] and "Керівник" not in [f.name for f in n.fields("Учні")]
assert {(r["Прізвище"], r["Клас"]) for r in n.rows("Учні")} == before, "дані не загубились"
n.update("Класи", n.find_by_label("Класи", "5-А"), {"Керівник": "Нова Н. Н."})
assert len(n.rows("Класи")) == 3 and not n.normalize_hints("Учні")
print("НОРМАЛІЗАЦІЯ OK")

# --- програма МОН: заперечення, запити-дії, SQL-пісочниця, N:M, класифікація зв'язків ---
from shkola_office.data.query import action, restore_snapshot, run_sql_write  # noqa: E402
cols, res = Query(j, {"table": "Оцінки", "fields": [{"name": "Предмет"}],
                      "where": [{"field": "Предмет", "op": "не містить", "value": "мова"}]}).run()
assert res and all("мова" not in r[0] for r in res)
n_math = len([r for r in j.rows("Оцінки") if r["Предмет"] == "Математика"])
pv = action(j, {"table": "Оцінки", "action": "update", "set": {"Бал": "12"},
                "where": [{"field": "Предмет", "op": "=", "value": "Математика"}]}, preview=True)
assert pv["count"] == n_math and pv["sql"].startswith('UPDATE "Оцінки" SET "Бал" = ?')
action(j, {"table": "Оцінки", "action": "update", "set": {"Бал": "12"},
           "where": [{"field": "Предмет", "op": "=", "value": "Математика"}]})
assert all(r["Бал"] == 12 for r in j.rows("Оцінки") if r["Предмет"] == "Математика")
j.undo()
assert not all(r["Бал"] == 12 for r in j.rows("Оцінки") if r["Предмет"] == "Математика"), "одна дія = один крок назад"
try:
    action(j, {"table": "Оцінки", "action": "update", "set": {"Бал": "багато"}, "where": []})
    raise AssertionError("type check")
except DataError:
    pass
before = len(j.rows("Оцінки"))
d = action(j, {"table": "Оцінки", "action": "delete", "where": [{"field": "Бал", "op": "<", "value": "5"}]})
assert len(j.rows("Оцінки")) == before - d["count"]
j.undo()
assert len(j.rows("Оцінки")) == before
assert run_sql_write(j, 'UPDATE "Оцінки" SET "Бал" = 1') == before
assert all(r["Бал"] == 1 for r in j.rows("Оцінки"))
assert restore_snapshot(j) and not all(r["Бал"] == 1 for r in j.rows("Оцінки"))
for bad in ('DROP TABLE "Учні"', 'DELETE FROM _id_fields', 'UPDATE "Учні" SET "Ім\'я"=1; DELETE FROM "Учні"'):
    try:
        run_sql_write(j, bad)
        raise AssertionError(bad)
    except DataError:
        pass
j.create_table("Гуртки", [Field("Назва", required=True, unique=True)])
j.insert("Гуртки", {"Назва": "Робототехніка"})
jt = j.add_many_to_many("Учні", "Гуртки")
lf = [f.name for f in j.fields(jt)]
j.insert(jt, {"Учні": 1, "Гуртки": 1})
try:
    j.insert(jt, {lf[0]: 1, lf[1]: 1})
    raise AssertionError("N:M без дублів")
except Exception:
    pass
kinds = {(r["from"], r["to"], r["kind"]) for r in j.relations()}
assert ("Учні", "Гуртки", "N:M") in kinds and ("Учні", "Оцінки", "1:N") in kinds, kinds
assert any(r["required"] for r in j.relations() if r["kind"] == "1:N")
print("ПРОГРАМА МОН (запити-дії, N:M) OK")

# --- навчальний шар: SQL кожної дії, завдання з перевіркою ---
from shkola_office.data.tasks import check, explain_sql, open_task, save_task  # noqa: E402
j.update("Учні", 1, {"Ім'я": "Остап"})
s = explain_sql(j.history(limit=1)[0])
assert s == 'UPDATE "Учні" SET "Ім\'я" = \'Остап\' WHERE id = 1;', s
etalon = {"table": "Оцінки", "fields": [{"name": "Учень"}, {"name": "Бал"}], "where": [{"field": "Бал", "op": "≥", "value": "10"}]}
save_task(j, D / "zavd.itask", "Відмінники", "Виведіть учнів і бали, де бал не менше 10", etalon)
sdb, task = open_task(D / "zavd.itask", D / "student")
assert task["title"] == "Відмінники" and "Виведіть" in task["condition"]
ok, msg = check(sdb, task, 'SELECT "Учень", "Бал" FROM "_id_v_Оцінки" WHERE "Бал" >= 10')
assert ok, msg
ok, msg = check(sdb, task, 'SELECT "Учень", "Бал" FROM "_id_v_Оцінки" WHERE "Бал" > 10')
assert not ok and "Рядків" in msg, msg
ok, msg = check(sdb, task, {"table": "Оцінки", "fields": [{"name": "Учень"}], "where": []})
assert not ok and "Стовпців" in msg
print("НАВЧАЛЬНИЙ ШАР OK")
