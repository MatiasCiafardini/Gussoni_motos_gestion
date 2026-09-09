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
            if factura.get("estado_id") == self._estado_error_getter():
                wsfe_result = self._consultar_autorizacion_existente(
                    repo=repo,
                    auth=auth,
                    factura=factura,
                )
                if wsfe_result is None:
                    if not self._es_seguro_reintentar_mismo_numero(repo, auth, factura):
                        return self._guardar_estado_incierto(
                            db,
                            factura_id,
                            factura,
                            RuntimeError("ARCA todavia no permitio confirmar el comprobante"),
                        )
                    try:
                        wsfe_result = self._wsfe.solicitar_cae(
                            auth=auth,
                            factura=factura,
                            items=items,
                        )
                    except Exception as retry_error:
                        db.rollback()
                        repo = self._repo_factory(db)
                        wsfe_result = self._consultar_autorizacion_existente(
                            repo=repo,
                            auth=auth,
                            factura=factura,
                        )
                        if wsfe_result is None:
                            return self._guardar_estado_incierto(
                                db, factura_id, factura, retry_error
                            )
            else:
                try:
                    wsfe_result = self._wsfe.solicitar_cae(
                        auth=auth,
                        factura=factura,
                        items=items,
                    )
                except Exception as e:
                    logger.exception("Error al invocar WSFE.solicitar_cae para factura {}", factura_id)
                    db.rollback()
                    repo = self._repo_factory(db)
                    wsfe_result = self._consultar_autorizacion_existente(
                        repo=repo,
                        auth=auth,
                        factura=factura,
                    )
                    if wsfe_result is None:
                        return self._guardar_estado_incierto(db, factura_id, factura, e)

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

    def _guardar_estado_incierto(
        self,
        db: Session,
        factura_id: int,
        factura: Dict[str, Any],
        error: Exception,
    ) -> Dict[str, Any]:
        """No revierte la operacion cuando no sabemos si ARCA la proceso."""
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
                f"[ARCA] Pendiente de confirmacion por error de comunicacion: {error}",
            )
            self._audit.registrar(
                db,
                entidad="facturas",
                entidad_id=factura_id,
                accion="ARCA_ESTADO_INCIERTO",
                datos_previos={"estado_id": factura.get("estado_id")},
                datos_nuevos={"estado_id": estado_error, "cae": None},
                contexto={"mensaje": str(error), "efectos_revertidos": False},
            )
            db.commit()
        except Exception:
            logger.exception("Error guardando estado incierto para factura {}", factura_id)
            db.rollback()

        return {
            "factura_id": factura_id,
            "aprobada": False,
            "rechazada": False,
            "estado_incierto": True,
            "cae": None,
            "fecha_cae": None,
            "vto_cae": None,
            "estado_id": estado_error,
            "errores": [],
            "observaciones": [],
            "mensaje": (
                "No se pudo confirmar la respuesta de ARCA. La factura conserva su numero "
                "y queda pendiente de verificacion; no vuelva a emitirla."
            ),
        }

    def _consultar_autorizacion_existente(
        self,
        *,
        repo: FacturasRepository,
        auth: ArcaAuthData,
        factura: Dict[str, Any],
    ) -> Optional[ArcaWSFEResult]:
        """Recupera el CAE si ARCA autorizo antes de cortarse la respuesta."""
        consultar = getattr(self._wsfe, "fe_comp_consultar", None)
        if not callable(consultar):
            return None
        try:
            tipo = repo.get_tipo_comprobante_by_id(factura.get("tipo_comprobante_id"))
            codigo = tipo["codigo"]
            cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)
            raw = consultar(
                auth=auth,
                cbte_tipo=cbte_tipo,
                pto_vta=int(factura.get("punto_venta") or 0),
                cbte_nro=int(factura.get("numero") or 0),
            )
            resultado = str(raw.get("resultado") or "").strip().upper()
            cae = raw.get("cae")
            if resultado != "A" or not cae:
                return None
            return ArcaWSFEResult(
                aprobada=True,
                rechazada=False,
                cae=str(cae),
                fecha_cae=raw.get("fecha_cae"),
                vto_cae=raw.get("vto_cae"),
                errores=raw.get("errores") or [],
                observaciones=raw.get("observaciones") or [],
                mensaje="Comprobante recuperado desde ARCA despues de una respuesta interrumpida.",
            )
        except Exception as consulta_error:
            logger.warning("No se pudo reconciliar mediante FECompConsultar: {}", consulta_error)
            return None

    def _es_seguro_reintentar_mismo_numero(
        self,
        repo: FacturasRepository,
        auth: ArcaAuthData,
        factura: Dict[str, Any],
    ) -> bool:
        """Solo reintenta si ARCA espera exactamente el numero ya reservado."""
        consultar_ultimo = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
        if not callable(consultar_ultimo):
            return False
        try:
            tipo = repo.get_tipo_comprobante_by_id(factura.get("tipo_comprobante_id"))
            codigo = tipo["codigo"]
            cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)
            raw = consultar_ultimo(
                auth=auth,
                cbte_tipo=cbte_tipo,
                pto_vta=int(factura.get("punto_venta") or 0),
            )
            ultimo = self._parse_ultimo_autorizado(raw)
            numero = int(factura.get("numero") or 0)
            return numero > 0 and ultimo + 1 == numero
        except Exception as error:
            logger.warning("No se pudo validar un reintento seguro: {}", error)
            return False

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
