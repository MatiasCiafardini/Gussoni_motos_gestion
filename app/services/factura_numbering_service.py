from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.database import SessionLocal
from app.integrations.arca.wsaa_client import ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient
from app.repositories.facturas_repository import FacturasRepository


class FacturaNumberingService:
    """Resuelve numeracion de comprobantes sin tocar el flujo de facturacion."""

    def __init__(self, *, wsaa, wsfe, repo_factory: Callable[[Session], FacturasRepository]):
        self._wsaa = wsaa
        self._wsfe = wsfe
        self._repo_factory = repo_factory

    def sugerir_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> int:
        logger.debug("sugerir_proximo_numero tipo={} pto_vta={}", tipo_comprobante_id, pto_vta)

        if not tipo_comprobante_id or not pto_vta:
            return 1

        try:
            pto = int(pto_vta)
        except Exception:
            pto = 1

        db = SessionLocal()
        try:
            repo = self._repo_factory(db)
            nro = self.obtener_proximo_numero_real(db, repo, tipo_comprobante_id, pto)
            logger.debug("sugerir_proximo_numero -> {}", nro)
            return nro
        finally:
            db.close()

    def diagnosticar_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "tipo_comprobante_id": tipo_comprobante_id,
            "pto_vta": None,
            "proximo": 1,
            "origen": "BD",
            "ws_ok": False,
            "ultimo_afip": None,
            "proximo_local": None,
            "errores": [],
            "mensaje": "",
        }

        if not tipo_comprobante_id or not pto_vta:
            info["mensaje"] = "Tipo de comprobante y punto de venta son obligatorios."
            return info

        try:
            pto = int(pto_vta)
            info["pto_vta"] = pto
        except Exception:
            info["mensaje"] = f"Punto de venta invalido: {pto_vta!r}"
            return info

        db = SessionLocal()
        try:
            repo = self._repo_factory(db)
            ultimo_afip: Optional[int] = None
            ws_llamado_ok = False

            fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
            if callable(fe_ult):
                try:
                    auth: ArcaAuthData = self._wsaa.get_auth()
                    tipo = repo.get_tipo_comprobante_by_id(tipo_comprobante_id)
                    codigo = tipo["codigo"]
                    cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)
                    ultimo_afip_raw = fe_ult(auth=auth, cbte_tipo=cbte_tipo, pto_vta=pto)
                    ws_llamado_ok = True
                    ultimo_afip = self._parse_ultimo_afip(ultimo_afip_raw, info["errores"])
                except Exception as e:
                    ws_llamado_ok = False
                    ultimo_afip = None
                    info["errores"].append(f"Error al llamar FECompUltimoAutorizado: {e!r}")
            else:
                info["errores"].append("El cliente WSFE no implementa fe_comp_ultimo_autorizado().")

            if ws_llamado_ok:
                info["ws_ok"] = True
                if ultimo_afip is None:
                    ultimo_afip = 0
                proximo_afip = ultimo_afip + 1
                try:
                    proximo_local = repo.get_next_numero(tipo_comprobante_id, pto)
                except Exception as e:
                    proximo_local = 1
                    info["errores"].append(
                        f"Error al consultar numeracion local (repo.get_next_numero): {e!r}"
                    )
                if not proximo_local or proximo_local <= 0:
                    proximo_local = 1
                proximo = proximo_afip
                info["ultimo_afip"] = ultimo_afip
                info["proximo"] = proximo
                info["proximo_local"] = proximo_local
                info["origen"] = f"AFIP ({settings.ARCA_ENV})"
                info["mensaje"] = (
                    f"AFIP respondio correctamente. Ultimo autorizado: {ultimo_afip}. "
                    f"Proximo AFIP: {proximo_afip}. Proximo local: {proximo_local}. "
                    f"Proximo a usar: {proximo}. "
                    "La numeracion local queda solo como referencia diagnostica."
                )
                if proximo_local != proximo_afip:
                    info["errores"].append(
                        "La numeracion local no coincide con ARCA. "
                        "Se usara el proximo informado por ARCA para evitar rechazo 10016."
                    )
                return info

            try:
                proximo_local = repo.get_next_numero(tipo_comprobante_id, pto)
            except Exception as e:
                proximo_local = 1
                info["errores"].append(
                    f"Error al consultar numeracion local (repo.get_next_numero): {e!r}"
                )

            if not proximo_local or proximo_local <= 0:
                proximo_local = 1

            info["proximo"] = proximo_local
            info["proximo_local"] = proximo_local
            info["origen"] = "BD"
            info["mensaje"] = (
                "No se pudo usar AFIP (FECompUltimoAutorizado). "
                "Se devolvio el proximo numero segun la base de datos local."
            )
            return info
        finally:
            db.close()

    def obtener_proximo_numero_real(
        self,
        db: Session,
        repo: FacturasRepository,
        tipo_comprobante_id: int,
        pto_vta: int,
    ) -> int:
        logger.debug(
            "_obtener_proximo_numero_real tipo={} pto_vta={}",
            tipo_comprobante_id,
            pto_vta,
        )

        ultimo_afip: Optional[int] = None
        ws_llamado_ok = False
        fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)

        if callable(fe_ult):
            try:
                auth: ArcaAuthData = self._wsaa.get_auth()
                tipo = repo.get_tipo_comprobante_by_id(tipo_comprobante_id)
                codigo = tipo["codigo"]
                cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)
                ultimo_afip_raw = fe_ult(auth=auth, cbte_tipo=cbte_tipo, pto_vta=pto_vta)
                ws_llamado_ok = True
                ultimo_afip = self._parse_ultimo_afip(ultimo_afip_raw, [])
            except Exception as e:
                logger.warning("Error al llamar FECompUltimoAutorizado: {}", e)
                ws_llamado_ok = False
                ultimo_afip = None
        else:
            logger.debug("_wsfe no tiene fe_comp_ultimo_autorizado")

        if ws_llamado_ok:
            if ultimo_afip is None:
                ultimo_afip = 0
            proximo_afip = ultimo_afip + 1
            try:
                proximo_local = repo.get_next_numero(tipo_comprobante_id, pto_vta)
            except Exception as e:
                logger.warning("Error en repo.get_next_numero: {}", e)
                proximo_local = 1

            if not proximo_local or proximo_local <= 0:
                proximo_local = 1

            proximo = proximo_afip
            if proximo_local != proximo_afip:
                logger.warning(
                    "Numeracion local ({}) no coincide con proximo ARCA ({}) en {}; usando ARCA para evitar rechazo 10016.",
                    proximo_local,
                    proximo_afip,
                    settings.ARCA_ENV,
                )
            return proximo

        try:
            proximo_local = repo.get_next_numero(tipo_comprobante_id, pto_vta)
        except Exception as e:
            logger.warning("Error en repo.get_next_numero: {}", e)
            proximo_local = 1

        if not proximo_local or proximo_local <= 0:
            proximo_local = 1

        return proximo_local

    @staticmethod
    def _parse_ultimo_afip(value: Any, errores: list[str]) -> Optional[int]:
        if isinstance(value, dict):
            for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                if key in value and value[key] is not None:
                    try:
                        return int(value[key])
                    except Exception as e:
                        errores.append(
                            f"Error parseando campo {key} de FECompUltimoAutorizado: {e!r}"
                        )
            return None

        try:
            return int(value or 0)
        except Exception as e:
            errores.append(f"Error parseando respuesta FECompUltimoAutorizado: {e!r}")
            return None
