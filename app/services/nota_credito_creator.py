from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List

from sqlalchemy.orm import Session

from app.data.database import SessionLocal
from app.integrations.arca.wsaa_client import ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient, ArcaWSFEResult
from app.repositories.facturas_repository import FacturasRepository
from app.services.audit_log_service import AuditLogService


class NotaCreditoCreator:
    """Genera y autoriza notas de credito sin ampliar FacturasService."""

    def __init__(
        self,
        *,
        wsaa,
        wsfe,
        repo_factory: Callable[[Session], FacturasRepository],
        condicion_resolver: Callable[[Session, Dict[str, Any]], int | None],
        nc_effects_processor: Callable[[Session, int], None],
        estado_borrador_getter: Callable[[], int],
        estado_autorizada_getter: Callable[[], int],
        estado_rechazada_getter: Callable[[], int],
        estado_error_getter: Callable[[], int],
        audit: AuditLogService | None = None,
    ) -> None:
        self._wsaa = wsaa
        self._wsfe = wsfe
        self._repo_factory = repo_factory
        self._condicion_resolver = condicion_resolver
        self._nc_effects_processor = nc_effects_processor
        self._estado_borrador_getter = estado_borrador_getter
        self._estado_autorizada_getter = estado_autorizada_getter
        self._estado_rechazada_getter = estado_rechazada_getter
        self._estado_error_getter = estado_error_getter
        self._audit = audit or AuditLogService()

    def generar_nota_credito(self, factura_id: int) -> Dict[str, Any]:
        db = SessionLocal()

        try:
            repo = self._repo_factory(db)

            factura_original = repo.get_by_id(factura_id)
            if not factura_original:
                raise ValueError(f"Factura {factura_id} no encontrada.")

            items_original = repo.get_detalle_by_factura(factura_id)
            if not items_original:
                raise ValueError("La factura original no tiene items.")

            tipo_orig = repo.get_tipo_comprobante_by_id(
                factura_original["tipo_comprobante_id"]
            )
            if not tipo_orig:
                raise ValueError("Tipo comprobante original no encontrado.")

            pto_vta = factura_original.get("punto_venta")
            tipo_nc = repo.get_tipo_nota_credito_por_letra(tipo_orig["letra"])
            if not tipo_nc:
                raise ValueError("No se encontro tipo de Nota de Credito correspondiente.")

            tipo_nc_id = tipo_nc["id"]
            tipo_nc_codigo = tipo_nc["codigo"]
            numero_nc = self._obtener_numero_nc(repo, tipo_nc_id, tipo_nc_codigo, pto_vta)
            items_nc, subtotal_nc, iva_nc, total_nc = self._generar_items_nc(items_original)

            hoy = date.today().strftime("%Y-%m-%d")
            observ = (
                f"NC que anula factura {tipo_orig['codigo']} "
                f"{str(pto_vta).zfill(4)}-{factura_original.get('numero')}"
            )

            condicion_iva_nc_id = self._condicion_resolver(db, factura_original)
            cabecera_nc = {
                "tipo_comprobante_id": tipo_nc_id,
                "numero": int(numero_nc),
                "fecha_emision": hoy,
                "punto_venta": int(pto_vta),
                "moneda": factura_original.get("moneda", "ARS"),
                "cotizacion": float(factura_original.get("cotizacion") or 1.0),
                "cae": None,
                "fecha_cae": None,
                "vto_cae": None,
                "subtotal": subtotal_nc,
                "iva": iva_nc,
                "total": total_nc,
                "observaciones": observ,
                "estado_id": self._estado_borrador_getter(),
                "cliente_id": factura_original.get("cliente_id"),
                "condicion_iva_receptor_id": condicion_iva_nc_id,
                "cbte_asoc_tipo": tipo_orig["codigo"],
                "cbte_asoc_pto_vta": int(pto_vta),
                "cbte_asoc_numero": factura_original.get("numero"),
                "factura_origen_id": factura_id,
            }

            nc_id = repo.insert_factura(cabecera_nc)
            repo.insert_detalle(nc_id, items_nc)

            auth: ArcaAuthData = self._wsaa.get_auth()
            factura_nc = repo.get_by_id(nc_id)
            factura_nc["condicion_iva_receptor_id"] = condicion_iva_nc_id
            factura_nc["cbte_asoc_tipo"] = tipo_orig["codigo"]

            wsfe_result: ArcaWSFEResult = self._wsfe.solicitar_cae(
                auth=auth,
                factura=factura_nc,
                items=items_nc,
            )

            if wsfe_result.aprobada:
                estado_nc = self._estado_autorizada_getter()
            elif wsfe_result.rechazada:
                estado_nc = self._estado_rechazada_getter()
            else:
                estado_nc = self._estado_error_getter()

            repo.actualizar_cae_y_estado(
                factura_id=nc_id,
                cae=wsfe_result.cae,
                fecha_cae=wsfe_result.fecha_cae,
                vto_cae=wsfe_result.vto_cae,
                estado_id=estado_nc,
            )

            if wsfe_result.aprobada:
                self._nc_effects_processor(db, nc_id)

            self._audit.registrar(
                db,
                entidad="facturas",
                entidad_id=nc_id,
                accion="NOTA_CREDITO_GENERADA",
                datos_nuevos={
                    "factura_origen_id": factura_id,
                    "aprobada": wsfe_result.aprobada,
                    "estado_id": estado_nc,
                    "cae": wsfe_result.cae,
                },
            )

            db.commit()
            nc_header = repo.get_by_id(nc_id)

            return {
                "factura_original_id": factura_id,
                "nc_id": nc_id,
                "aprobada": wsfe_result.aprobada,
                "rechazada": wsfe_result.rechazada,
                "cae": wsfe_result.cae,
                "fecha_cae": wsfe_result.fecha_cae,
                "vto_cae": wsfe_result.vto_cae,
                "mensaje": wsfe_result.mensaje,
                "nc_tipo_codigo": tipo_nc_codigo,
                "nc_letra": tipo_nc["letra"],
                "nc_pto_vta": nc_header.get("punto_venta"),
                "nc_numero": nc_header.get("numero"),
                "nc_total": nc_header.get("total"),
            }

        except Exception as ex:
            db.rollback()
            return {
                "factura_original_id": factura_id,
                "nc_id": None,
                "aprobada": False,
                "rechazada": False,
                "mensaje": f"Error interno en generar_nota_credito: {ex}",
            }

        finally:
            db.close()

    def _obtener_numero_nc(
        self,
        repo: FacturasRepository,
        tipo_nc_id: int,
        tipo_nc_codigo: str,
        pto_vta: Any,
    ) -> int:
        ultimo_autorizado = 0
        try:
            fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
            if callable(fe_ult):
                auth: ArcaAuthData = self._wsaa.get_auth()
                cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(
                    tipo_nc_codigo
                )
                ult_raw = fe_ult(auth=auth, cbte_tipo=cbte_tipo, pto_vta=int(pto_vta))
                if isinstance(ult_raw, dict):
                    for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                        if key in ult_raw and ult_raw[key] is not None:
                            ultimo_autorizado = int(ult_raw[key])
                            break
                else:
                    ultimo_autorizado = int(ult_raw or 0)
        except Exception:
            ultimo_autorizado = 0

        proximo_afip = ultimo_autorizado + 1
        try:
            proximo_local = repo.get_next_numero(tipo_nc_id, int(pto_vta))
        except Exception:
            proximo_local = 1
        if not proximo_local or proximo_local <= 0:
            proximo_local = 1
        return max(proximo_afip, proximo_local)

    @staticmethod
    def _generar_items_nc(items_original: List[Dict[str, Any]]):
        items_nc: List[Dict[str, Any]] = []
        subtotal_nc = 0.0
        iva_nc = 0.0
        total_nc = 0.0

        for it in items_original:
            cantidad = float(it.get("cantidad") or 0.0)
            precio_unit = float(it.get("precio_unitario") or 0.0)
            alic_iva = float(it.get("alicuota_iva") or 0.0)
            neto_nc = -abs(float(it.get("importe_neto") or 0.0))
            iva_nc_item = -abs(float(it.get("importe_iva") or 0.0))
            total_nc_item = -abs(float(it.get("importe_total") or 0.0))

            subtotal_nc += neto_nc
            iva_nc += iva_nc_item
            total_nc += total_nc_item

            items_nc.append(
                {
                    "item_tipo": it.get("item_tipo", "VEHICULO"),
                    "vehiculo_id": it.get("vehiculo_id"),
                    "descripcion": it.get("descripcion"),
                    "cantidad": -abs(cantidad),
                    "precio_unitario": precio_unit,
                    "alicuota_iva": alic_iva,
                    "importe_neto": neto_nc,
                    "importe_iva": iva_nc_item,
                    "importe_total": total_nc_item,
                }
            )

        return items_nc, subtotal_nc, iva_nc, total_nc
