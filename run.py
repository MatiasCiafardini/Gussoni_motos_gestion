from app.ui.main import main
from app.core.updater import check_for_update

try:
    update = check_for_update()
    if update:
        print("Hay una actualización disponible:", update["version"])
    else:
        print("La aplicación está actualizada")
except Exception as e:
    print("Error al buscar actualizaciones:", e)
if __name__ == "__main__":
    main()

