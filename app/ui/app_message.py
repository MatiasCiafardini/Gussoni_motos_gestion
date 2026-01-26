# app/ui/app_message.py
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer

from app.ui.widgets.app_message_dialog import AppMessageDialog
from app.ui.notify import NotifyPopup


# ----------------- Modales "grandes" -----------------


def info(parent: Optional[QWidget], title: str, text: str) -> None:
    AppMessageDialog.info(parent, title, text)


def warning(parent: Optional[QWidget], title: str, text: str) -> None:
    AppMessageDialog.warning(parent, title, text)


def error(parent: Optional[QWidget], title: str, text: str) -> None:
    AppMessageDialog.error(parent, title, text)


def confirm(
    parent: Optional[Widget],
    title: str,
    text: str,
    *,
    ok_text: str = "Aceptar",
    cancel_text: str = "Cancelar",
) -> bool:
    return AppMessageDialog.confirm(
        parent,
        title,
        text,
        ok_text=ok_text,
        cancel_text=cancel_text,
    )


# ----------------- Nuevo: aviso tipo "toast" -----------------


def toast(
    parent: Optional[QWidget],
    text: str,
    *,
    kind: str = "info",   # info | success | warning | error
    msec: int = 3000,
    pos: str = "middle",
) -> None:
    """
    Aviso corto no modal (toast).
    - No bloquea la app
    - No tiene botones
    - Se cierra solo

    kind: info | success | warning | error
    """
    popup = NotifyPopup(text, kind, parent)
    popup.show_centered(msec=msec, pos=pos)

    QTimer.singleShot(msec, popup.close)