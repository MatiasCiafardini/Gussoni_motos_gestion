from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple


def validar_factura(
    *,
    cabecera: Dict[str, Any],
    items: List[Dict[str, Any]],
    es_nota_credito: bool,
    comprobante_nc_id: Optional[Any] = None,
) -> Tuple[bool, List[str]]:
    """
    Validaciones de Facturas y Notas de Crédito.
    Devuelve (ok, errores)
    """

    errores: List[str] = []

    # ---------- Cabecera ----------
    if not cabecera.get("tipo"):
        errores.append("Seleccioná el tipo de comprobante.")

    if not cabecera.get("pto_vta"):
        errores.append("Seleccioná el punto de venta.")

    if not cabecera.get("fecha_emision"):
        errores.append("Ingresá la fecha de emisión.")

    if not cabecera.get("cliente_id"):
        errores.append("Seleccioná un cliente.")

    if not cabecera.get("condicion_iva_receptor_id"):
        errores.append("Seleccioná la condición frente al IVA del receptor.")
    print(es_nota_credito)
    # ---------- Nota de Crédito ----------
    if es_nota_credito:
        if comprobante_nc_id in (None, "", 0, "0"):
            errores.append(
                "Seleccioná el comprobante a asociar a la Nota de Crédito."
            )
        return (len(errores) == 0), errores

    # ---------- Factura normal ----------
    if not items:
        errores.append("Agregá al menos un vehículo en el detalle.")
        return False, errores

    for idx, it in enumerate(items, start=1):
        if not it.get("vehiculo_id"):
            errores.append(f"Fila {idx}: falta seleccionar el vehículo.")
            break

        cantidad = it.get("cantidad") or 0
        precio = it.get("precio_unitario") or 0
        total = it.get("importe_total") or 0

        if es_nota_credito:
            # En NC el total debe ser negativo
            if total >= 0:
                errores.append(
                    f"Fila {idx}: el importe total debe ser negativo en una Nota de Crédito."
                )
                break
        else:
            # Factura normal
            if cantidad <= 0:
                errores.append(f"Fila {idx}: la cantidad debe ser mayor a 0.")
                break

            if precio <= 0:
                errores.append(f"Fila {idx}: el precio unitario debe ser mayor a 0.")
                break


    return (len(errores) == 0), errores
