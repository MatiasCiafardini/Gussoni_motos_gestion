from functools import wraps
from PySide6.QtWidgets import QApplication, QMainWindow

def with_loading(text: str = "Procesando..."):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):

            mw = getattr(self, "main_window", None)

            # fallback: obtener el MainWindow real
            if mw is None:
                w = self.window()
                if isinstance(w, QMainWindow) and hasattr(w, "loading"):
                    mw = w

            if mw and hasattr(mw, "loading"):
                mw.loading.lbl_text.setText(text)
                mw.loading.show_overlay()
                QApplication.processEvents()

            try:
                return func(self, *args, **kwargs)
            finally:
                if mw and hasattr(mw, "loading"):
                    mw.loading.hide_overlay()
                    QApplication.processEvents()

        return wrapper
    return decorator
