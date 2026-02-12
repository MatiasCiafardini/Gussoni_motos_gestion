from __future__ import annotations
from typing import Dict, Tuple
from app.services.catalogos_service import CatalogosService


def validar_cliente(data: Dict) -> Tuple[bool, Dict[str, str]]:
    errs: Dict[str, str] = {}

    if not data.get("nombre"):
        errs["nombre"] = "El nombre es obligatorio."

    tipo_doc_id = data.get("tipo_doc_id")
    catalogos = CatalogosService()

    if not tipo_doc_id:
        errs["tipo_doc_id"] = "Seleccioná el tipo de documento."

    nro_doc = data.get("nro_doc")
    if not nro_doc:
        errs["nro_doc"] = "Ingresá el número de documento."
    else:
        if not nro_doc.isdigit():
            errs["nro_doc"] = "El número de documento debe contener sólo números."

        if tipo_doc_id:
            if catalogos.es_dni(tipo_doc_id):
                if not (1 <= len(nro_doc) <= 8):
                    errs["nro_doc"] = "El DNI debe tener entre 1 y 8 dígitos."

            elif catalogos.es_cuit(tipo_doc_id) or catalogos.es_cuil(tipo_doc_id):
                if len(nro_doc) != 11:
                    errs["nro_doc"] = "El CUIT/CUIL debe tener 11 dígitos."

            else:
                if len(nro_doc) > 20:
                    errs["nro_doc"] = "El documento puede tener hasta 20 caracteres."


    email = data.get("email")
    if email:
        if "@" not in email or "." not in email.split("@")[-1]:
            errs["email"] = "Email inválido."

    if data.get("estado_id") is None:
        errs["estado_id"] = "Seleccioná el estado del cliente."

    return (len(errs) == 0, errs)
