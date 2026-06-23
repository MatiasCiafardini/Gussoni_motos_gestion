from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.data.database import SessionLocal
from app.integrations.arca.wsaa_client import ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient, ArcaWSFEResult
from app.repositories.facturas_repository import FacturasRepository
from app.services.audit_log_service import AuditLogService


class ArcaAuthorizationService:
    """Autoriza facturas en ARCA sin mezclar reglas de facturacion general."""

    def __init__(
        self,
        *,
        wsaa,
        wsfe,
        repo_factory: Callable[[Session], FacturasRepository],
        detalle_getter: Callable[[Session, int], List[Dict[str, Any]]],
        condicion_resolver: Callable[[Session, Dict[str, Any]], Optional[int]],
        observaciones_updater: Callable[[Session, int, str], None],
        error_cleaner: Callable[[Exception], str],
        estado_autorizada_getter: Callable[[], int],
        estado_rechazada_getter: Callable[[], int],
        estado_error_getter: Callable[[], int],
        rejected_effects_processor: Optional[Callable[[Session, int], None]] = None,
    ) -> None:
        self._wsaa = wsaa
        self._wsfe = wsfe
        self._repo_factory = repo_factory
        self._detalle_getter = detalle_getter
        self._condicion_resolver = condicion_resolver
        self._observaciones_updater = observaciones_updater
        self._error_cleaner = error_cleaner
        self._estado_autorizada_getter = estado_autorizada_getter
        self._estado_rechazada_getter = estado_rechazada_getter
        self._estado_error_getter = estado_error_getter
        self._rejected_effects_processor = rejected_effects_processor
        self._audit = AuditLogService()

    def autorizar_factura(self, factura_id: int) -> Dict[str, Any]:
        db = SessionLocal()
        factura = None
        try:
            repo = self._repo_factory(db)

            factura = repo.get_by_id(factura_id)
            logger.debug("Factura {} leida para autorizar", factura_id)

            if not factura:
                raise ValueError(f"Factura {factura_id} no encontrada.")

            condicion_iva_receptor_id = self._condicion_resolver(db, factura)
            factura["condicion_iva_receptor_id"] = condicion_iva_receptor_id

            if factura.get("cae") and factura.get("estado_id") == self._estado_autorizada_getter():
                return {
                    "factura_id": factura_id,
                    "ya_autorizada": True,
                    "aprobada": True,
                    "rechazada": False,
                    "cae": factura.get("cae"),
                    "fecha_cae": factura.get("fecha_cae"),
                    "vto_cae": factura.get("vto_cae"),
                    "estado_id": factura.get("estado_id"),
                    "estado_nombre": factura.get("estado_nombre"),
                    "errores": [],
                    "observaciones": [],
                    "mensaje": "La factura ya se encuentra autorizada.",
                }

            self._log_ultimo_autorizado(repo, factura)

            items = self._detalle_getter(db, factura_id)
            if not items:
                raise ValueError("La factura no tiene items en el detalle.")

            auth: ArcaAuthData = self._wsaa.get_auth()

            try:
                wsfe_result: ArcaWSFEResult = self._wsfe.solicitar_cae(
                    auth=auth,
                    factura=factura,
                    items=items,
                )
            except Exception as e:
                logger.exception("Error al invocar WSFE.solicitar_cae para factura {}", factura_id)
                db.rollback()
                estado_error = self._estado_error_getter()

                try:
                    repo = self._repo_factory(db)
                    repo.actualizar_cae_y_estado(
                        factura_id=factura_id,
                        cae=None,
                        fecha_cae=None,
                        vto_cae=None,
                        estado_id=estado_error,
                    )
                    self._observaciones_updater(
                        db,
                        factura_id,
                        f"[ARCA] Error de comunicacion: {e}",
                    )
                    if self._rejected_effects_processor:
                        self._rejected_effects_processor(
                            db,
                            factura_id,
                            motivo="Error de comunicacion ARCA",
                        )
                    self._audit.registrar(
                        db,
                        entidad="facturas",
                        entidad_id=factura_id,
                        accion="ARCA_ERROR_COMUNICACION",
                        datos_previos={"estado_id": factura.get("estado_id") if factura else None},
                        datos_nuevos={"estado_id": estado_error, "cae": None},
                        contexto={"mensaje": str(e), "efectos_revertidos": bool(self._rejected_effects_processor)},
                    )
                    db.commit()
                except Exception:
                    logger.exception("Error revirtiendo efectos por fallo ARCA para factura {}", factura_id)
                    db.rollback()

                return {
                    "factura_id": factura_id,
                    "aprobada": False,
                    "rechazada": False,
                    "cae": None,
                    "fecha_cae": None,
                    "vto_cae": None,
                    "estado_id": estado_error,
                    "errores": [],
                    "observaciones": [],
                    "mensaje": self._error_cleaner(e),
                }

            if wsfe_result.aprobada:
                nuevo_estado = self._estado_autorizada_getter()
            elif wsfe_result.rechazada:
                nuevo_estado = self._estado_rechazada_getter()
            else:
                nuevo_estado = self._estado_error_getter()
            logger.debug("Factura {} -> nuevo estado {}", factura_id, nuevo_estado)

            repo.actualizar_cae_y_estado(
                factura_id=factura_id,
                cae=wsfe_result.cae,
                fecha_cae=wsfe_result.fecha_cae,
                vto_cae=wsfe_result.vto_cae,
                estado_id=nuevo_estado,
            )
            logger.debug("Factura {} cabecera actualizada con CAE/estado", factura_id)

            if not wsfe_result.aprobada:
                texto_obs = self._build_rechazo_observaciones(wsfe_result)
                if texto_obs:
                    self._observaciones_updater(db, factura_id, texto_obs)

            if wsfe_result.rechazada and self._rejected_effects_processor:
                self._rejected_effects_processor(db, factura_id)

            self._audit.registrar(
                db,
                entidad="facturas",
                entidad_id=factura_id,
                accion="ARCA_AUTORIZACION",
                datos_previos={"estado_id": factura.get("estado_id")},
                datos_nuevos={
                    "estado_id": nuevo_estado,
                    "aprobada": wsfe_result.aprobada,
                    "rechazada": wsfe_result.rechazada,
                    "cae": wsfe_result.cae,
                },
                contexto={
                    "errores": wsfe_result.errores or [],
                    "observaciones": wsfe_result.observaciones or [],
                    "mensaje": wsfe_result.mensaje,
                },
            )

            db.commit()
            if wsfe_result.aprobada:
                logger.info("Factura {} autorizada en ARCA. CAE={}", factura_id, wsfe_result.cae)
            elif wsfe_result.rechazada:
                logger.warning("Factura {} rechazada por ARCA: {}", factura_id, wsfe_result.mensaje)
            else:
                logger.warning("Factura {} sin aprobacion ARCA: {}", factura_id, wsfe_result.mensaje)

            return {
                "factura_id": factura_id,
                "aprobada": wsfe_result.aprobada,
                "rechazada": wsfe_result.rechazada,
                "cae": wsfe_result.cae,
                "fecha_cae": wsfe_result.fecha_cae,
                "vto_cae": wsfe_result.vto_cae,
                "estado_id": nuevo_estado,
                "errores": wsfe_result.errores or [],
                "observaciones": wsfe_result.observaciones or [],
                "mensaje": wsfe_result.mensaje,
            }

        except Exception as ex:
            logger.exception("Error en autorizar_factura para factura {}", factura_id)
            db.rollback()
            return {
                "factura_id": factura_id,
                "aprobada": False,
                "rechazada": False,
                "cae": None,
                "fecha_cae": None,
                "vto_cae": None,
                "estado_id": factura.get("estado_id") if factura else None,
                "errores": [],
                "observaciones": [],
                "mensaje": self._error_cleaner(ex),
            }
        finally:
            db.close()

    def _log_ultimo_autorizado(
        self,
        repo: FacturasRepository,
        factura: Dict[str, Any],
    ) -> None:
        try:
            fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
            if not callable(fe_ult):
                return

            auth_debug: ArcaAuthData = self._wsaa.get_auth()
            tipo = repo.get_tipo_comprobante_by_id(factura.get("tipo_comprobante_id"))
            codigo = tipo["codigo"]
            cbte_tipo_dbg = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)
            pto_dbg = int(factura.get("punto_venta") or 0)
            ult_raw = fe_ult(
                auth=auth_debug,
                cbte_tipo=cbte_tipo_dbg,
                pto_vta=pto_dbg,
            )
            ult_nro = self._parse_ultimo_autorizado(ult_raw)
            logger.debug(
                "AFIP ultimo={} espera proximo={} numero_local={}",
                ult_nro,
                ult_nro + 1,
                factura.get("numero"),
            )
        except Exception as e:
            logger.warning("Error consultando FECompUltimoAutorizado: {}", e)

    @staticmethod
    def _parse_ultimo_autorizado(value: Any) -> int:
        if isinstance(value, dict):
            for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                if key in value and value[key] is not None:
                    try:
                        return int(value[key])
                    except Exception:
                        continue
            return 0

        try:
            return int(value or 0)
        except Exception:
            return 0

    @staticmethod
    def _build_rechazo_observaciones(wsfe_result: ArcaWSFEResult) -> str:
        partes: List[str] = []

        if wsfe_result.mensaje:
            partes.append(wsfe_result.mensaje.strip())

        if wsfe_result.errores:
            partes.append(
                "Errores ARCA:\n" + "\n".join(f"- {e}" for e in wsfe_result.errores)
            )

        if wsfe_result.observaciones:
            partes.append(
                "Observaciones ARCA:\n"
                + "\n".join(f"- {o}" for o in wsfe_result.observaciones)
            )

        return "\n".join(p for p in partes if p).strip()
