from __future__ import annotations
from typing import Dict, Tuple


def validar_cliente(data: Dict) -> Tuple[bool, Dict[str, str]]:
    """
    Validaciones comunes para Alta y Edición de Clientes.
    Devuelve (ok, errores_por_campo)
    """
    errs: Dict[str, str] = {}

    # -------- Nombre --------
    if not data.get("nombre"):
        errs["nombre"] = "El nombre es obligatorio."

    # -------- Tipo doc --------
    tipo_doc = data.get("tipo_doc")
    if not tipo_doc:
        errs["tipo_doc"] = "Seleccioná el tipo de documento."

    # -------- Nro doc --------
    nro_doc = data.get("nro_doc")
    if not nro_doc:
        errs["nro_doc"] = "Ingresá el número de documento."
    else:
        if not nro_doc.isdigit():
            errs["nro_doc"] = "El número de documento debe contener sólo números."

        if tipo_doc == "DNI" and not (1 <= len(nro_doc) <= 8):
            errs["nro_doc"] = "El DNI debe tener entre 1 y 8 dígitos."

        if tipo_doc in ("CUIT", "CUIL") and len(nro_doc) != 11:
            errs["nro_doc"] = "El CUIT/CUIL debe tener 11 dígitos."

        if tipo_doc not in ("DNI", "CUIT", "CUIL") and len(nro_doc) > 20:
            errs["nro_doc"] = "El documento puede tener hasta 20 caracteres."

    # -------- Email --------
    email = data.get("email")
    if email:
        if "@" not in email or "." not in email.split("@")[-1]:
            errs["email"] = "Email inválido."

    # -------- Estado --------
    if data.get("estado_id") is None:
        errs["estado_id"] = "Seleccioná el estado del cliente."

    return (len(errs) == 0, errs)
