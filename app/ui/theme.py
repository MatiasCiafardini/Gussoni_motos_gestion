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

/* CTA principal (compat: #Primary y #BtnPrimary) */
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

/* Botón “fantasma” (para Limpiar / naveg.) */
QPushButton#BtnGhost {{
    background: {p['bg']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px 12px;
    transition: all 0.15s ease;
}}

QPushButton#BtnGhost:hover {{
    background: #eef1f5;        /* leve aclarado al hover */
    border-color: #cfd5db;
}}
QPushButton#BtnGhost:pressed {{
    background: #e6e9ee;        /* tono más oscuro al presionar */
    border-color: #c6ccd4;
}}
QPushButton#BtnGhost:disabled {{
    color: {p['muted']};
    background: {p['bg']};
    border-color: {p['border']};
}}

/* Botón plano (paginación) */
QPushButton#BtnFlat {{
    background: transparent;
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 10px;
}}

/* =========================
   Quitar borde de foco en botones
   ========================= */
QPushButton:focus {{
    outline: none;
}}
QPushButton:focus-visible {{
    outline: none;
}}


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
    left: 10px; top: -6px; padding: 0 6px;
    color: {p['secondary']};
    background: transparent;
}}

/* =========================
   Inputs (base)
   ========================= */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {p['white']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 8px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {p['secondary']};
    outline: none;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled {{
    color: {p['muted']};
    background: {p['bg']};
}}

/* =========================
   Date inputs (QDateEdit)
   ========================= */
QDateEdit {{
    /* hereda base de Inputs; solo afinamos detalles */
    padding-right: 10px;       /* espacio cómodo */
    min-height: 36px;
}}

/* Ocultar flechitas de subir/bajar */
QDateEdit::up-button, QDateEdit::down-button {{
    width: 0px; height: 0px;
    border: none; margin: 0; padding: 0;
}}

/* Ocultar el triángulo del drop-down (dejamos solo click en el campo para abrir calendario) */
QDateEdit::drop-down {{
    width: 0px;
    border: none;
}}

/* Calendario popup */
QCalendarWidget QWidget {{
    background: {PALETTE['white']};
    color: {PALETTE['ink']};
}}
QCalendarWidget QToolButton {{
    background: {PALETTE['bg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 4px 8px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background: #eef1f5;
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {PALETTE['white']};
    selection-background-color: {PALETTE['secondary']};
    selection-color: {PALETTE['white']};
    gridline-color: {PALETTE['border']};
}}



/* =========================
   Combos de Filtros (bonitos)
   ========================= */
/* El page setea objectName="FilterCombo" y usa QListView#ComboPopup como popup */
QComboBox#FilterCombo {{
    background: {p['white']};
    color: {p['ink']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 6px 36px 6px 10px;  /* espacio derecha para drop-down */
    min-height: 36px;
}}
QComboBox#FilterCombo:hover {{
    background: #fcfcfe;
    border-color: #cfd5db;
}}
QComboBox#FilterCombo:focus {{
    border-color: {p['secondary']};
}}
QComboBox#FilterCombo:disabled {{
    color: {p['muted']};
    background: {p['bg']};
}}

QComboBox#FilterCombo::drop-down {{
    width: 32px;
    border-left: 1px solid {p['border']};
    margin-left: 6px;
}}
/* Si usás un recurso SVG, descomentá y ajustá la ruta:
QComboBox#FilterCombo::down-arrow {{
    image: url(:/icons/chevron-down.svg);
}}
*/
QComboBox#FilterCombo::down-arrow {{
    /* fallback al arrow por defecto del sistema */
    image: none;
}}

/* Popup del combo (aplica aunque no tenga setView, pero optimizado para QListView#ComboPopup) */
QComboBox#FilterCombo QAbstractItemView {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    outline: 0;
    selection-background-color: rgba(31,31,46,0.08);
    selection-color: {p['ink']};
}}
QListView#ComboPopup {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 6px;
}}
QListView#ComboPopup::item {{
    padding: 8px 10px;
    border-radius: 8px;
}}
QListView#ComboPopup::item:selected {{
    background: rgba(31,31,46,0.08);
    color: {p['ink']};
}}
QListView#ComboPopup::item:hover {{
    background: #f3f4f7;
}}

/* =========================
   Tablas
   ========================= */
QTableView {{
    background: {p['white']};
    color: {p['ink']};
    gridline-color: {p['border']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    selection-background-color: rgba(31,31,46,0.10);
    selection-color: {p['ink']};
}}
QTableView#DataTable {{  /* id específico por si querés tunear aparte */ }}

/* Tabla base (si la usan en páginas) */
QTableView#DataTable, QTableWidget#DataTable {{
    background: #FFFFFF; 
    border: 1px solid #E5E7EB; 
    border-radius: 12px;
    gridline-color: #ECECEC; 
    alternate-background-color: #FAFAFD;}}
QHeaderView::section {{
    text-align:left;
    background: {p['ink']};
    color: {p['white']}; 
    border: none; 
    padding: 8px 10px;
    font-size: 13px; 
    font-weight: 600;
}}
QHeaderView {{
    text-align:left;
}}
        

/* =========================
   Cards / Panels
   ========================= */
QFrame#Card, QFrame#Panel {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 12px;
}}
QLabel#KpiValue {{ color: {p['ink']}; 
}}


/* =========================
   Diálogo bonito (ConfirmDialog)
   ========================= */
QFrame#DialogPanel {{
    background: {p['white']};
    border: 1px solid {p['border']};
    border-radius: 12px;
}}
#NiceDialog QLabel#DialogTitle {{
    font-weight: 700;
    font-size: 15px;
    color: {p['ink']};
}}
#NiceDialog QLabel#DialogText {{
    font-size: 13px;
    color: {p['ink']};
}}
#NiceDialog QLabel#DialogInfo {{
    font-size: 12px;
    color: {p['secondary']};
}}
#NiceDialog QLabel#DialogIcon {{
    font-size: 18px; /* tamaño del emoji/icono */
}}

/* =========================
   Configuración – OptionCard minimal
   ========================= */
QPushButton#CfgOption {{
    background: #ffffff;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 14px;
}}
QPushButton#CfgOption:hover {{
    border-color: #D1D5DB;              /* leve énfasis */
    background: #dddddd;
}}
QPushButton#CfgOption:pressed {{
    background: #F8FAFC;
}}

/* Contenido */
QPushButton#CfgOption QLabel#CfgOptionIcon {{
    font-size: 40px;                     /* si usa emoji */
    color: #6B7280;
}}
QPushButton#CfgOption QLabel#CfgOptionTitle {{
    font-size: 14px;
    font-weight: 700;
    color: #1F2937; /* ink-like */
}}

/* Sombra muy sutil (fake) para plataformas sin efecto nativo) */
QPushButton#CfgOption {{
    box-shadow: 0px 6px 16px rgba(0,0,0,0.10);   /* Qt ignora, pero sirve en algunos estilos */
}}
/* La elevación real visual la logramos con el contraste del borde + bg del layout; 
   si querés más punch, podés sumar QGraphicsDropShadowEffect desde código. */



"""



def apply_theme(app: QApplication, base_font_pt: int = 11) -> None:
    f = QFont(); f.setFamily("Segoe UI"); f.setPointSize(base_font_pt)
    app.setFont(f)

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
