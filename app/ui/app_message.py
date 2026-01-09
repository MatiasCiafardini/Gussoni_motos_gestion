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


def critical(
    parent: Optional[QWidget],
    text: str,
    *,
    msec: int = 2000,
) -> None:
    """
    Aviso corto de validación / warning:
    - No es modal.
    - No tiene botones.
    - Se cierra solo luego de `msec` ms (por defecto 2 segundos).

    Ejemplo:
        app_message.warning_toast(self, "Seleccioná un punto de venta.")
    """
    popup = NotifyPopup(text, "warning", parent)
    popup.show_centered()

    # Auto-cierre luego de msec ms
    QTimer.singleShot(msec, popup.close)
