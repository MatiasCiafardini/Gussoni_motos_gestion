from functools import wraps
from PySide6.QtWidgets import QApplication

def with_loading(text: str = "Procesando..."):
    """
    Decorador para métodos de UI que tengan self.loading_overlay definido.
    Muestra el overlay mientras se ejecuta la función decorada y lo oculta al finalizar.
    Uso:
        @with_loading("Buscando...")
        def reload(self): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            overlay = getattr(self, "loading_overlay", None)
            if overlay:
                overlay.lbl_text.setText(text)
                overlay.show_overlay()
                QApplication.processEvents()
            try:
                return func(self, *args, **kwargs)
            finally:
                if overlay:
                    overlay.hide_overlay()
                    QApplication.processEvents()
        return wrapper
    return decorator
