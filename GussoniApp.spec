from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

APP_NAME = "GussoniApp_1.0.21"

reportlab_hidden = collect_submodules("reportlab")
mysql_hidden = collect_submodules("mysql")
keyring_hidden = collect_submodules("keyring")

crypto_hidden = [
    "cryptography.hazmat.backends.openssl.backend",
]

qt_bins = collect_dynamic_libs("PySide6")

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[
        *qt_bins,
        ('app/tools/openssl', 'app/tools/openssl'),
    ],
    datas=[
        ('app/assets', 'assets'),
    ],
    hiddenimports=[
        *reportlab_hidden,
        *mysql_hidden,
        *crypto_hidden,
        *keyring_hidden,
        'pkg_resources',
        'requests',
        'csv',
        'encodings',
        'openpyxl',
    ],
    excludes=[
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtPdf',
        'PySide6.QtCharts',
        'tkinter',
        'pytest',
        'unittest',
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    console=False,
    debug=False,
    upx=True,
    icon='app/assets/logo.ico',
)
