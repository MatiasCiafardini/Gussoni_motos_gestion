from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QApplication

PALETTE = {
    "ink": "#1f1f2e",
    "secondary": "#6c757d",
    "muted": "#adb5bd",
    "border": "#dee2e6",
    "bg": "#f8f9fa",
    "white": "#ffffff",
}


def _build_qss(p=PALETTE) -> str:
    return f"""
/* =========================
   Reset / Tipografía básica
   ========================= */
QLabel {{ background: transparent; color: {p['ink']}; }}

/* QTable corner sin iconos (lupa) */
QTableCornerButton::section {{
    background: {p['bg']};
    border: 1px solid {p['border']};
    image: none;
}}
/* =========================
   Tooltips
   ========================= */
QToolTip {{
    background-color: #E0F2FE;      /* celestito suave */
    color: #0F172A;                 /* texto oscuro */
    border: 1px solid #7DD3FC;      /* borde celeste */
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 0.95em;
}}

/* =========================
   Sidebar
   ========================= */
QFrame#Sidebar {{
    background: {p['ink']};
    border-right: 1px solid {p['border']};
}}
QFrame#Sidebar QLabel {{ color: {p['bg']}; }}
QFrame#Sidebar QPushButton {{
    background: transparent;
    color: {p['bg']};
    border: 1px solid {p['secondary']};
    border-radius: 10px;
    padding: 8px 12px;
    text-align: left;
}}
QFrame#Sidebar QPushButton:hover {{
    background: {p['secondary']};
    color: {p['bg']};
}}
QFrame#Sidebar QPushButton:checked {{
    background: {p['secondary']};
    color: {p['bg']};
}}
QFrame#Sidebar QPushButton:pressed {{
    background: {p['ink']};
    border-color: {p['ink']};
}}
QPushButton#SideLogout {{
    color: #E8EAED; 
    background: #2A3040; 
    border: 1px solid #3A4050;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: left; 
    font-size: 1em;
}}
QPushButton#SideLogout:hover {{ background: #343B4D; }}
QPushButton#SideLogout:pressed {{ background: #6C5CE7; }}

/* =========================
   Botones
   ========================= */
QPushButton {{
    background: {p['white']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px 12px;
}}
QPushButton:hover {{ background: {p['bg']}; }}
QPushButton:disabled {{ color: {p['muted']}; background: {p['bg']}; }}

QPushButton#Primary, QPushButton#BtnPrimary {{
    background: {p['ink']};
    color: {p['white']};
    border: 1px solid {p['ink']};
}}
QPushButton#Primary:hover, QPushButton#BtnPrimary:hover {{
    background: {p['secondary']};
    border-color: {p['secondary']};
}}
QPushButton#Primary:pressed, QPushButton#BtnPrimary:pressed {{
    background: {p['ink']};
    border-color: {p['ink']};
}}

QPushButton#BtnGhost {{
    background: {p['bg']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px 12px;
}}
QPushButton#BtnGhost:hover {{
    background: #eef1f5;
    border-color: #cfd5db;
}}
QPushButton#BtnGhost:pressed {{
    background: #e6e9ee;
    border-color: #c6ccd4;
}}
QPushButton#BtnGhost:disabled {{
    color: {p['muted']};
    background: {p['bg']};
    border-color: {p['border']};
}}

QPushButton#BtnFlat {{
    background: transparent;
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 10px;
}}

QPushButton:focus {{ outline: none; }}
QPushButton:focus-visible {{ outline: none; }}

/* =========================
   GroupBox
   ========================= */
QGroupBox {{
    border: 1px solid {p['border']};
    border-radius: 10px;
    margin-top: 12px;
    background: {p['white']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: -6px;
    padding: 0 6px;
    color: {p['secondary']};
}}

/* =========================
   Inputs
   ========================= */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {p['white']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 8px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {p['secondary']};
}}
QLineEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled {{
    color: {p['muted']};
    background: {p['bg']};
}}

/* =========================
   Login
   ========================= */
QDialog#LoginDialog {{ background: {p['bg']}; }}
QFrame#LoginCard {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 16px;
}}
QLabel#LoginTitle {{
    font-size: 1.6em;
    font-weight: 600;
}}
QLabel#LoginSubtitle {{
    color: {p['secondary']};
    font-size: 1em;
}}
QLabel#LoginError {{
    color: #d64545;
    font-weight: 600;
}}

/* =========================
   Tablas
   ========================= */
QTableView {{background: {p['white']};
    color: {p['ink']};
    gridline-color: #E5E7EB;                /* líneas divisorias */
    border: 1px solid {p['border']};
    border-radius: 8px;
    selection-background-color: rgba(31,31,46,0.10);
    selection-color: {p['ink']};
    alternate-background-color: #F3F4F6;   /* 👈 gris claro interlineado */}}

QHeaderView::section {{
    background: {p['ink']};
    color: {p['white']};
    border: none;
    padding: 8px 10px;
    font-size: 0.9em;
    font-weight: 600;
}}

/* =========================
   Cards / Panels
   ========================= */
QFrame#Card, QFrame#Panel {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 12px;
}}

/* =========================
   Dialogs
   ========================= */
#NiceDialog QLabel#DialogTitle {{
    font-weight: 700;
    font-size: 1.4em;
}}

#NiceDialog QLabel#DialogText {{
    font-size: 1.05em;
}}

#NiceDialog QLabel#DialogInfo {{
    font-size: 0.95em;
    color: {p['secondary']};
}}

#NiceDialog QLabel#DialogIcon {{
    font-size: 1.6em;
}}

QDialog#NiceDialog {{
    background: transparent;
}}

QFrame#DialogPanel {{
    background: #ffffff;
    border-radius: 14px;
}}

QLabel#DialogTitle {{
    font-size: 1.4em;
    font-weight: 600;
}}

QLabel#DialogText {{
    font-size: 1.05em;
}}

QLabel#DialogInfo {{
    color: #555;
    font-size: 0.95em;
}}


/* =========================
   COMBOBOX (INPUT)
   ========================= */
QComboBox {{
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 34px;
    color: #111827;
}}

QComboBox:hover {{
    border-color: #C7D2FE;
}}

QComboBox:focus {{
    border-color: #6C5CE7;
    outline: none;
}}

/* Flecha */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #E5E7EB;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6B7280;
}}

/* =========================
   COMBOBOX POPUP (DESPLEGABLE)
   ========================= */
QComboBox QAbstractItemView {{
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: #EEF2FF;
    selection-color: #1E1B4B;
}}

/* Items */
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 6px;
    color: #111827;
}}

/* Hover */
QComboBox QAbstractItemView::item:hover {{
    background-color: #E0E7FF;
}}

/* Selected */
QComboBox QAbstractItemView::item:selected {{
    background-color: #6C5CE7;
    color: white;
}}
 QMenu {{
    font-size: 2em;
    background-color: #111827;
    color: #FFFFFF;
    border: 1px solid #1f2937;
    padding: 6px;
}}
QMenu::item {{
    font-size: 2em;
    padding: 6px 12px;
    background-color: transparent;
}}
QMenu::item:selected {{
    background-color: #1f2937;
    color: #FFFFFF;
}}


"""


def apply_theme(
    app: QApplication,
    base_font_pt: int = 11,
    scale: float = 1.0
) -> None:
    """
    Aplica tema visual y tipografía global.
    - base_font_pt: tamaño base (pt)
    - scale: factor de escala (1.0 = default)
    """

    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSizeF(base_font_pt * scale)
    app.setFont(font)

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(PALETTE["bg"]))
    pal.setColor(QPalette.Base, QColor(PALETTE["white"]))
    pal.setColor(QPalette.Text, QColor(PALETTE["ink"]))
    pal.setColor(QPalette.ButtonText, QColor(PALETTE["ink"]))
    pal.setColor(QPalette.Button, QColor(PALETTE["white"]))
    pal.setColor(QPalette.WindowText, QColor(PALETTE["ink"]))
    pal.setColor(QPalette.ToolTipBase, QColor(PALETTE["bg"]))
    pal.setColor(QPalette.ToolTipText, QColor(PALETTE["ink"]))
    pal.setColor(QPalette.Highlight, QColor(PALETTE["secondary"]))
    pal.setColor(QPalette.HighlightedText, QColor(PALETTE["white"]))
    app.setPalette(pal)

    app.setStyleSheet(_build_qss(PALETTE))
