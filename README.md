# MotoAgency Desk (Windows, PySide6 + MySQL)

Sistema de gestión para agencia de motos (Argentina).

## Tecnologías
- Python 3.11+
- PySide6 (UI)
- SQLAlchemy 2.x (MySQL)
- python-dotenv
- loguru
- reportlab

## Estructura
```
app/
  core/
    config.py          # carga .env y constantes
    logging_setup.py   # configuración de loguru
  data/
    database.py        # conexión SQLAlchemy (engine + Session)
  repositories/
    vehiculos_repository.py
    ventas_repository.py
  services/
    dashboard_service.py
  ui/
    main.py            # punto de entrada de la app
    main_window.py     # QMainWindow + navegación
    pages/
      dashboard_page.py
      placeholder_page.py
    widgets/
      sidebar.py
reports/
.env.example
requirements.txt
run.py
```

## Variables de entorno (.env)
Cree un archivo `.env` en la raíz con:
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=secret
DB_NAME=motoagency
DB_POOL_SIZE=5
DB_POOL_TIMEOUT=30
```

## Ejecutar
```bash
pip install -r requirements.txt
python run.py
```
