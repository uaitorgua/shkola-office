"""Бібліотека векторних об'єктів InterSlide: пошук українською за назвою/тегами/темою, перефарбування під тему."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..config import OFFICE_ASSETS

LIB_DIR = OFFICE_ASSETS / "library"
TOKENS = ("#010101", "#020202", "#030303")      # основний, акцент, світла заливка (tools/make_library.py)


@lru_cache(maxsize=1)
def items() -> tuple[dict, ...]:
    f = LIB_DIR / "index.json"
    return tuple(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else ()


def topics() -> list[str]:
    return list(dict.fromkeys(i["topic"] for i in items()))


def search(query: str = "", topic: str = "") -> list[dict]:
    words = [w for w in query.lower().split() if w]
    out = []
    for it in items():
        if topic and it["topic"] != topic:
            continue
        hay = f'{it["title"]} {it["tags"]} {it["topic"]} {it["id"]}'.lower()
        if all(w in hay for w in words):
            out.append(it)
    return out


def recolor(svg: str, main: str, accent: str, fill: str) -> str:
    for tok, col in zip(TOKENS, (main, accent, fill)):
        svg = svg.replace(tok, col)
    return svg


def svg_text(item: dict) -> str:
    return (LIB_DIR / item["file"]).read_text(encoding="utf-8")


def themed_svg(item: dict, theme) -> bytes:
    """theme — themes.Theme або None (кольори ГС за замовчуванням)."""
    if theme is None:
        main, acc, fill = "#135548", "#e0a526", "#e3f1ec"
    else:
        main, acc, fill = theme.title, theme.accent, theme.card
    return recolor(svg_text(item), main, acc, fill).encode("utf-8")
