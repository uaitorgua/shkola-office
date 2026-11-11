"""Автозбереження для всіх редакторів «Офісу ШКОЛА».
Кожні 2 хв (і при закритті вікна), якщо є зміни:
  1) файл, з яким працюють, зберігається в ТОМУ Ж форматі (DOCX лишається DOCX, XLSX — XLSX, PPTX — PPTX, власні — власними);
     PDF/HTML-квіз не перезаписуємо (це вивід, не робочий файл);
  2) завжди — резервна копія у власному форматі в %APPDATA%/ofis-shkola/autosave/ (для нового документа лише вона).
Після звичайного закриття зі збереженням копія видаляється; якщо програма впала — при наступному старті
«Офіс ШКОЛА» пропонує відновити.
Вікно-редактор надає: path, is_dirty(), mark_clean(), write_own(path), save_to(path), OWN_EXT, KIND."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from .. import config

INTERVAL_MS = 120_000
WORKING = {"text": (".docx", ".itext", ".html", ".htm", ".txt"), "tab": (".xlsx", ".csv", ".itab"),
           "slide": (".islide", ".pptx")}


def autosave_dir() -> Path:
    d = config.DATA_DIR / "autosave"
    d.mkdir(parents=True, exist_ok=True)
    return d


class AutoSave(QObject):
    def __init__(self, win, interval_ms: int = INTERVAL_MS) -> None:
        super().__init__(win)
        self.win = win
        self.id = uuid.uuid4().hex[:12]
        self.timer = QTimer(self, interval=interval_ms, timeout=self.tick)
        self.timer.start()
        self.last = 0.0

    @property
    def backup(self) -> Path:
        return autosave_dir() / f"{self.id}{self.win.OWN_EXT}"

    def tick(self) -> bool:
        w = self.win
        if not w.is_dirty():
            return False
        try:
            w.write_own(self.backup)
            (autosave_dir() / f"{self.id}.json").write_text(json.dumps(
                {"kind": w.KIND, "file": self.backup.name, "path": str(w.path or ""), "time": time.time()},
                ensure_ascii=False), encoding="utf-8")
            p = w.path
            if p and p.suffix.lower() in WORKING.get(w.KIND, ()):
                if w.save_to(p):
                    w.mark_clean()
            self.last = time.time()
            if hasattr(w, "statusBar"):
                w.statusBar().showMessage(f"Автозбережено {time.strftime('%H:%M')}", 5000)
            return True
        except Exception as e:  # noqa: BLE001 — автозбереження не має валити редактор
            if hasattr(w, "statusBar"):
                w.statusBar().showMessage(f"Автозбереження не вдалося: {e}", 8000)
            return False

    def discard(self) -> None:
        """Документ збережено й закрито нормально — резервна копія не потрібна."""
        for f in (self.backup, autosave_dir() / f"{self.id}.json"):
            f.unlink(missing_ok=True)


def pending() -> list[dict]:
    """Незакриті копії після збою (для «Відновити незбережене?»)."""
    out = []
    for j in sorted(autosave_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(j.read_text(encoding="utf-8"))
            if (autosave_dir() / d["file"]).exists():
                out.append({**d, "meta": j, "backup": autosave_dir() / d["file"]})
        except (OSError, ValueError, KeyError):
            continue
    return out


def forget(item: dict) -> None:
    item["meta"].unlink(missing_ok=True)
    item["backup"].unlink(missing_ok=True)
