"""Офіс ШКОЛА: спільні редактори InterText (документи) і InterTab (таблиці) для застосунків ГС «УАІТ».
Правки редакторів — лише тут; застосунки підключають репозиторій як git-підмодуль."""

__version__ = "1.0.0"


def configure(**kw) -> None:
    """APP_NAME, APP_ID, ASSETS, LOGO_SVG, LOGO_PNG, DATA_DIR — до першого імпорту shkola_office.ui.*"""
    from . import config
    for k, v in kw.items():
        if not hasattr(config, k):
            raise KeyError(k)
        setattr(config, k, v)
