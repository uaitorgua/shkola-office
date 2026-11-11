"""InterData: зразкові бази для уроків (усі дані вигадані)."""
from __future__ import annotations

import random

from .db import Database, Field

SAMPLES = ["Шкільна бібліотека", "Журнал оцінок"]
_SURN = ["Коваленко", "Бондар", "Ткаченко", "Шевчук", "Мельник", "Кравець", "Олійник", "Савчук", "Лисенко", "Руденко",
         "Мороз", "Поліщук", "Гончар", "Марченко", "Левченко", "Петренко"]
_NAMES = ["Олена", "Андрій", "Марія", "Дмитро", "Софія", "Максим", "Анна", "Іван", "Вікторія", "Назар", "Ірина", "Тарас"]


def build(db: Database, name: str) -> None:
    rnd = random.Random(2026)
    if name == "Шкільна бібліотека":
        db.create_table("Класи", [Field("Назва", unique=True, required=True), Field("Керівник")])
        for k, t in (("5-А", "Іваненко О. П."), ("6-Б", "Сидоренко Н. В."), ("7-А", "Гнатюк Л. М.")):
            db.insert("Класи", {"Назва": k, "Керівник": t})
        db.create_table("Читачі", [Field("Прізвище", required=True), Field("Ім'я"), Field("Клас", "link", link="Класи"),
                                   Field("Телефон батьків", "phone")])
        for i in range(12):
            db.insert("Читачі", {"Прізвище": _SURN[i], "Ім'я": rnd.choice(_NAMES), "Клас": rnd.choice(["5-А", "6-Б", "7-А"]),
                                 "Телефон батьків": f"+380 67 {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"})
        db.create_table("Книги", [Field("Назва", required=True), Field("Автор"),
                                  Field("Жанр", "choice", choices=["Казка", "Повість", "Поезія", "Пригоди", "Наука"]),
                                  Field("Рік", "integer"), Field("Примірників", "integer")])
        for t, a, g, y, n in (("Тигролови", "Іван Багряний", "Пригоди", 1944, 3), ("Кайдашева сім'я", "Іван Нечуй-Левицький", "Повість", 1879, 5),
                              ("Лісова пісня", "Леся Українка", "Поезія", 1911, 4), ("Захар Беркут", "Іван Франко", "Повість", 1883, 2),
                              ("Ліскові казки", "Народні", "Казка", 2001, 6), ("Космос для дітей", "Колектив", "Наука", 2020, 2)):
            db.insert("Книги", {"Назва": t, "Автор": a, "Жанр": g, "Рік": y, "Примірників": n})
        db.create_table("Видачі", [Field("Читач", "link", link="Читачі", required=True), Field("Книга", "link", link="Книги", required=True),
                                   Field("Видано", "date", required=True), Field("Повернуто", "bool")])
        for i in range(18):
            db.insert("Видачі", {"Читач": rnd.randint(1, 12), "Книга": rnd.randint(1, 6),
                                 "Видано": f"{rnd.randint(1, 28):02d}.{rnd.choice([9, 10, 11]):02d}.2026", "Повернуто": rnd.choice(["так", "ні"])})
    elif name == "Журнал оцінок":
        db.create_table("Учні", [Field("Прізвище", required=True), Field("Ім'я"), Field("Клас", "choice", choices=["7-А", "7-Б"])])
        for i in range(10):
            db.insert("Учні", {"Прізвище": _SURN[i], "Ім'я": rnd.choice(_NAMES), "Клас": rnd.choice(["7-А", "7-Б"])})
        db.create_table("Предмети", [Field("Назва", unique=True), Field("Вчитель")])
        for p, t in (("Математика", "Гнатюк Л. М."), ("Українська мова", "Іваненко О. П."), ("Інформатика", "Ковальчук Р. С.")):
            db.insert("Предмети", {"Назва": p, "Вчитель": t})
        db.create_table("Оцінки", [Field("Учень", "link", link="Учні", required=True), Field("Предмет", "link", link="Предмети", required=True),
                                   Field("Дата", "date"), Field("Бал", "integer", required=True),
                                   Field("Рівень", "formula", formula='ЯКЩО([Бал]>=10;"високий";ЯКЩО([Бал]>=7;"достатній";'
                                                                    'ЯКЩО([Бал]>=4;"середній";"початковий")))')])
        for i in range(40):
            db.insert("Оцінки", {"Учень": rnd.randint(1, 10), "Предмет": rnd.randint(1, 3),
                                 "Дата": f"{rnd.randint(1, 28):02d}.10.2026", "Бал": rnd.randint(3, 12)})
