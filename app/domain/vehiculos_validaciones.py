from typing import Dict, Any, Tuple

def validate_vehiculo(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errs: Dict[str, str] = {}

    if not data.get("marca"):
        errs["marca"] = "La marca es obligatoria."

    if not data.get("modelo"):
        errs["modelo"] = "El modelo es obligatorio."

    anio = data.get("anio")
    if not isinstance(anio, int) or not (1900 <= anio <= 2100):
        errs["anio"] = "El año debe estar entre 1900 y 2100."

    if not data.get("numero_cuadro"):
        errs["numero_cuadro"] = "El N° de cuadro es obligatorio."

    if not data.get("numero_motor"):
        errs["numero_motor"] = "El N° de motor es obligatorio."

    if not data.get("color_id"):
        errs["color_id"] = "Seleccioná un color."

    if not data.get("estado_stock_id"):
        errs["estado_stock_id"] = "Seleccioná el estado de stock."

    if not data.get("estado_moto_id"):
        errs["estado_moto_id"] = "Seleccioná la condición."

    precio = data.get("precio_lista")
    if not isinstance(precio, (int, float)) or precio <= 0:
        errs["precio_lista"] = "El precio debe ser mayor a 0."

    return (len(errs) == 0, errs)
