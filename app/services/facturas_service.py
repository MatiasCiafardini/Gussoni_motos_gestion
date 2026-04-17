from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import text

from loguru import logger

from app.data.database import SessionLocal
from app.repositories.facturas_repository import FacturasRepository
from app.services.catalogos_service import CatalogosService

# Integraciones ARCA / AFIP
from app.integrations.arca.wsaa_client import ArcaWSAAClient, ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient, ArcaWSFEResult

#ventas service
from app.services.ventas_service import VentasService


class FacturasService:
    """Orquesta casos de uso de Facturación (listado, detalle, alta, ARCA, etc.)."""

    # IDs según tu tabla 'estados' (tipo='facturas')
    # Estos valores pueden variar entre instalaciones; en __init__ se intenta
    # resolver por nombre desde la BD para evitar hardcodear IDs incorrectos.
    ESTADO_BORRADOR = 12
    ESTADO_PENDIENTE_AFIP = 13
    ESTADO_AUTORIZADA = 14
    ESTADO_RECHAZADA = 15
    ESTADO_ANULADA = 16
    ESTADO_ERROR_COMUNICACION = 18

    # Estado que se aplica a la factura original cuando una Nota de Crédito
    # es autorizada. Por defecto usamos 'Anulada' (16). Si en tu BD existe un
    # estado específico "Anulada por NC", se resolverá automáticamente.
    ESTADO_ANULADA_POR_NC = 16

    # Estado de venta (tipo='ventas') que se aplica al cancelar por NC.
    ESTADO_VENTA_CANCELADA = 33

    def __init__(self) -> None:
        # Servicio de catálogos con caché global (estados, tipos de comprobante, etc.).
        self._catalogos = CatalogosService()

        # Clientes de integración con ARCA
        # wsaa -> autenticación (token + sign)
        # wsfe -> facturación electrónica (CAE)
        self._wsaa = ArcaWSAAClient()
        self._wsfe = ArcaWSFEClient()

        # Ajustar IDs de estados por nombre (si existen en la BD)
        self._init_estado_ids()

    # -------------------- Infra --------------------

    def _repo(self, db: Optional[Session] = None) -> FacturasRepository:
        return FacturasRepository(db or SessionLocal())

    @staticmethod
    def _clean_error_message(ex: Exception) -> str:
        """Devuelve un mensaje legible para el usuario, ocultando detalles SQL internos."""
        from sqlalchemy.exc import OperationalError, IntegrityError
        if isinstance(ex, OperationalError):
            orig = getattr(ex, "orig", None)
            if orig and hasattr(orig, "args") and len(orig.args) >= 2:
                code = orig.args[0]
                if code == 1205:
                    return "Tiempo de espera agotado en la base de datos. Por favor reintentá en unos segundos."
                if code in (2003, 2006, 2013):
                    return "No se pudo conectar a la base de datos. Verificá la conexión de red."
                return f"Error de base de datos (código {code}). Contactá al soporte."
        if isinstance(ex, IntegrityError):
            return "Error de integridad en los datos. Verificá que no haya duplicados."
        msg = str(ex)
        if any(kw in msg for kw in ("[SQL:", "UPDATE ", "INSERT ", "SELECT ", "pymysql")):
            return "Error al guardar los datos. Por favor reintentá o contactá al soporte."
        return msg

    def _init_estado_ids(self) -> None:
        """Intenta resolver IDs de estados por nombre desde la BD.

        Esto evita errores cuando los IDs cambian entre instalaciones.
        Si la tabla/consulta falla, se mantienen los valores por defecto.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            estados_fact = repo.list_estados_facturas() or []
            por_nombre = {str(e.get("nombre", "")).strip().lower(): int(e.get("id")) for e in estados_fact if e.get("id") is not None}

            def pick(*names: str) -> Optional[int]:
                for n in names:
                    k = str(n).strip().lower()
                    if k in por_nombre:
                        return por_nombre[k]
                return None

            self.ESTADO_ANULADA = pick("Anulada") or self.ESTADO_ANULADA
            self.ESTADO_ANULADA_POR_NC = pick("Anulada por NC", "Anulada por N/C", "Anulada") or self.ESTADO_ANULADA_POR_NC

            # Resolver estado de ventas
            try:
                estados_venta = db.execute(
                    text("SELECT id, nombre FROM estados WHERE tipo = 'ventas'")
                ).mappings().all()
                por_nombre_venta = {str(e["nombre"]).strip().lower(): int(e["id"]) for e in estados_venta}
                self.ESTADO_VENTA_CANCELADA = (
                    por_nombre_venta.get("cancelada")
                    or por_nombre_venta.get("cancelado")
                    or self.ESTADO_VENTA_CANCELADA
                )
            except Exception:
                pass
        except Exception:
            logger.warning("No se pudieron resolver IDs de estados desde la BD; usando valores por defecto.")
        finally:
            db.close()

    # -------------------- Lookups (desde caché) --------------------

    def get_tipos_comprobante(self) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).list_tipos_comprobante()
        finally:
            db.close()

    def get_estados_facturas(self) -> List[Dict[str, Any]]:
        estados = self._catalogos.get_value_safe("estados_facturas")
        if estados:
            return estados

        db = SessionLocal()
        try:
            estados = self._repo(db).list_estados_facturas()
            self._catalogos.set("estados_facturas", estados)
            return estados
        finally:
            db.close()

    def get_puntos_venta(self) -> List[Dict[str, Any]]:
        """
        Devuelve la lista de puntos de venta para poblar el combo en la UI.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            fn = getattr(repo, "list_puntos_venta", None)
            if callable(fn):
                return fn()

            # Fallback: query directa
            rows = db.execute(
                text(
                    """
                    SELECT
                        idpunto_venta AS id,
                        punto_venta
                    FROM puntos_venta
                    ORDER BY punto_venta
                    """
                )
            ).mappings().all()

            return [dict(r) for r in rows]
        finally:
            db.close()

    def get_condiciones_iva_receptor(self) -> List[Dict[str, Any]]:
        """
        Devuelve la lista de condiciones frente al IVA del receptor para el combo.

        Prioridad:
        1) Tabla local 'condiciones_iva_receptor' (vía FacturasRepository).
        2) Llamado al WSFE (si hubiera un método paramétrico implementado).
        3) Fallback estático básico.
        """
        cache_key = "condiciones_iva_receptor"

        # 1) Cache en CatalogosService
        cached = self._catalogos_get_value_safe(cache_key)
        if cached:
            return cached

        condiciones: List[Dict[str, Any]] = []

        # 2) Intentar leer desde BD (tabla condiciones_iva_receptor)
        db = SessionLocal()
        try:
            repo = self._repo(db)
            fn = getattr(repo, "list_condiciones_iva_receptor", None)
            if callable(fn):
                condiciones = fn() or []
        except Exception:
            condiciones = []
        finally:
            db.close()

        # 3) (Opcional) Intentar desde ARCA (si tenés implementado fe_param_get_condicion_iva_receptor)
        if not condiciones:
            getter = getattr(self._wsfe, "fe_param_get_condicion_iva_receptor", None)
            if callable(getter):
                try:
                    auth: ArcaAuthData = self._wsaa.get_auth()
                    condiciones = getter(auth) or []
                except Exception:
                    condiciones = []

        # 4) Fallback local estático: IDs deben ser los reales de AFIP si querés
        if not condiciones:
            condiciones = [
                {"id": 1, "codigo": "RI", "descripcion": "IVA Responsable Inscripto"},
                {"id": 4, "codigo": "EX", "descripcion": "IVA Sujeto Exento"},
                {"id": 6, "codigo": "MT", "descripcion": "Responsable Monotributo"},
                {"id": 5, "codigo": "CF", "descripcion": "Consumidor Final"},
            ]

        # Cachear para próximas llamadas
        try:
            self._catalogos.set(cache_key, condiciones)
        except Exception:
            pass

        return condiciones

    # -------------------- Numeración --------------------

    def sugerir_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> int:
        """
        Devuelve el próximo número de factura según tipo y punto de venta.

        Ahora:
        - Intenta primero con AFIP (FECompUltimoAutorizado).
        - SOLO si AFIP falla (error de WS), cae a la BD.
        """
        logger.debug("sugerir_proximo_numero tipo={} pto_vta={}", tipo_comprobante_id, pto_vta)

        if not tipo_comprobante_id or not pto_vta:
            return 1

        try:
            pto = int(pto_vta)
        except Exception:
            pto = 1

        db = SessionLocal()
        try:
            repo = self._repo(db)
            nro = self._obtener_proximo_numero_real(db, repo, tipo_comprobante_id, pto)
            logger.debug("sugerir_proximo_numero → {}", nro)
            return nro
        finally:
            db.close()

    def diagnosticar_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> Dict[str, Any]:
        """
        Versión 'verbose' de la numeración para usar en la pantalla
        de Configuración ARCA.

        Devuelve un dict con:
          - tipo_comprobante_id, pto_vta
          - proximo: int
          - origen: 'AFIP' | 'BD'
          - ws_ok: bool
          - ultimo_afip: Optional[int]
          - proximo_local: Optional[int]
          - errores: List[str]
          - mensaje: str
        """
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
            info["mensaje"] = f"Punto de venta inválido: {pto_vta!r}"
            return info

        db = SessionLocal()
        try:
            repo = self._repo(db)

            # 1) Intentar AFIP primero
            ultimo_afip: Optional[int] = None
            ws_llamado_ok = False

            fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
            if callable(fe_ult):
                try:
                    auth: ArcaAuthData = self._wsaa.get_auth()
                    tipo = repo.get_tipo_comprobante_by_id(tipo_comprobante_id)
                    codigo = tipo["codigo"]

                    cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)



                    ultimo_afip_raw = fe_ult(
                        auth=auth,
                        cbte_tipo=cbte_tipo,
                        pto_vta=pto,
                    )
                    ws_llamado_ok = True

                    if isinstance(ultimo_afip_raw, dict):
                        for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                            if key in ultimo_afip_raw and ultimo_afip_raw[key] is not None:
                                try:
                                    ultimo_afip = int(ultimo_afip_raw[key])
                                    break
                                except Exception as e:
                                    info["errores"].append(
                                        f"Error parseando campo {key} de FECompUltimoAutorizado: {e!r}"
                                    )
                    else:
                        try:
                            ultimo_afip = int(ultimo_afip_raw or 0)
                        except Exception as e:
                            info["errores"].append(
                                f"Error parseando respuesta FECompUltimoAutorizado: {e!r}"
                            )
                            ultimo_afip = None
                except Exception as e:
                    ws_llamado_ok = False
                    ultimo_afip = None
                    info["errores"].append(
                        f"Error al llamar FECompUltimoAutorizado: {e!r}"
                    )
            else:
                info["errores"].append(
                    "El cliente WSFE no implementa fe_comp_ultimo_autorizado()."
                )

            # 2) Si el WS respondió OK, usamos SIEMPRE lo que diga AFIP
            if ws_llamado_ok:
                info["ws_ok"] = True
                if ultimo_afip is None:
                    ultimo_afip = 0
                proximo = ultimo_afip + 1
                info["ultimo_afip"] = ultimo_afip
                info["proximo"] = proximo
                info["origen"] = "AFIP"

                # También podemos calcular la referencia local, sin usarla como fuente
                try:
                    proximo_local = repo.get_next_numero(tipo_comprobante_id, pto)
                    info["proximo_local"] = proximo_local
                except Exception as e:
                    info["errores"].append(
                        f"Error al consultar numeración local (repo.get_next_numero): {e!r}"
                    )

                info["mensaje"] = (
                    f"AFIP respondió correctamente. Último autorizado: {ultimo_afip}. "
                    f"Próximo a usar según AFIP: {proximo}."
                )
                return info

            # 3) Si el WS falló, caemos a la BD
            try:
                proximo_local = repo.get_next_numero(tipo_comprobante_id, pto)
            except Exception as e:
                proximo_local = 1
                info["errores"].append(
                    f"Error al consultar numeración local (repo.get_next_numero): {e!r}"
                )

            if not proximo_local or proximo_local <= 0:
                proximo_local = 1

            info["proximo"] = proximo_local
            info["proximo_local"] = proximo_local
            info["origen"] = "BD"
            info["mensaje"] = (
                "No se pudo usar AFIP (FECompUltimoAutorizado). "
                "Se devolvió el próximo número según la base de datos local."
            )
            return info

        finally:
            db.close()

    def _obtener_proximo_numero_real(
        self,
        db: Session,
        repo: FacturasRepository,
        tipo_comprobante_id: int,
        pto_vta: int,
    ) -> int:
        """
        Calcula el próximo número de comprobante.

        PRIORIDAD AHORA:
        1) AFIP (FECompUltimoAutorizado)  -> (ultimo_afip o 0) + 1
           *Se usa SIEMPRE si el WS responde OK, aunque el último sea 0.*
        2) Si AFIP falla (error de WS): BD (repo.get_next_numero)
        """
        logger.debug("_obtener_proximo_numero_real tipo={} pto_vta={}", tipo_comprobante_id, pto_vta)

        # 1) Intentar AFIP primero
        ultimo_afip: Optional[int] = None
        ws_llamado_ok = False

        fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)

        if callable(fe_ult):
            try:
                # Auth ARCA
                auth: ArcaAuthData = self._wsaa.get_auth()

                tipo = repo.get_tipo_comprobante_by_id(tipo_comprobante_id)
                codigo = tipo["codigo"]

                cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo)




                ultimo_afip_raw = fe_ult(
                    auth=auth,
                    cbte_tipo=cbte_tipo,
                    pto_vta=pto_vta,
                )
                ws_llamado_ok = True

                # Puede venir int o dict, lo tratamos defensivo
                if isinstance(ultimo_afip_raw, dict):
                    for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                        if key in ultimo_afip_raw and ultimo_afip_raw[key] is not None:
                            try:
                                ultimo_afip = int(ultimo_afip_raw[key])
                                break
                            except Exception as e:
                                logger.debug("Error parseando campo {} de AFIP: {}", key, e)
                else:
                    try:
                        ultimo_afip = int(ultimo_afip_raw or 0)
                    except Exception as e:
                        logger.debug("Error parseando ultimo_afip_raw directo: {}", e)
                        ultimo_afip = None

            except Exception as e:
                logger.warning("Error al llamar FECompUltimoAutorizado: {}", e)
                ws_llamado_ok = False
                ultimo_afip = None
        else:
            logger.debug("_wsfe no tiene fe_comp_ultimo_autorizado")

        # Si el WS respondió OK, usamos SIEMPRE lo que diga AFIP
        if ws_llamado_ok:
            if ultimo_afip is None:
                ultimo_afip = 0
            proximo = ultimo_afip + 1
            return proximo

        # 2) Fallback: lo que tengas en BD
        proximo_local = 1
        try:
            proximo_local = repo.get_next_numero(tipo_comprobante_id, pto_vta)  # normalmente last_local + 1
        except Exception as e:
            logger.warning("Error en repo.get_next_numero: {}", e)
            proximo_local = 1

        if not proximo_local or proximo_local <= 0:
            proximo_local = 1

        return proximo_local

    # -------------------- Search / Read --------------------

    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            rows, total = repo.search(filtros, page=page, page_size=page_size)
            return rows, total
        finally:
            db.close()

    def get(self, factura_id: int) -> Optional[Dict[str, Any]]:
        """
        Devuelve la cabecera de factura enriquecida con datos de venta
        (forma de pago, cuotas, etc.).
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)

            fn = getattr(repo, "get_by_id_con_venta", None)
            if callable(fn):
                fac = fn(factura_id)
            else:
                fac = repo.get_by_id(factura_id)

            if fac:
                fac["forma_pago_texto"] = self._build_forma_pago_texto(fac)

            return fac
        finally:
            db.close()

    def _build_forma_pago_texto(self, row: Dict[str, Any]) -> str:
        nombre = str(row.get("forma_pago_nombre") or "").strip()
        if not nombre:
            return ""
    
        if nombre.lower() == "financiación":
            cuotas = row.get("cantidad_cuotas")
            importe_cuota = row.get("importe_cuota")
    
            partes = ["Financiación"]
            if cuotas:
                partes.append(f"{int(cuotas)} cuotas")
            if importe_cuota:
                partes.append(f"de ${float(importe_cuota):,.2f} c/u")

    
            return " – ".join(partes)
    
        return nombre
    
    def get_detalle(self, factura_id: int) -> List[Dict[str, Any]]:
        """
        Devuelve el detalle de la factura (facturas_detalle).
        Usado para la pantalla de consulta y para ARCA.
                """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.get_detalle_by_factura(factura_id)
        finally:
            db.close()

    # -------------------- Alta usada por facturas_agregar --------------------

    def create_factura_completa(
        self,
        cabecera: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> int:
        """
        Crea una factura con su detalle.
        - Normaliza datos
        - Completa estado inicial (Borrador)
        - Calcula subtotal, IVA y total (por si la UI no lo mandó)
        - Inserta factura + detalle
        - Devuelve el ID de la nueva factura
        """

        db = SessionLocal()
        try:
            repo = self._repo(db)

            # ---------------- Calcular totales ----------------
            subtotal = sum(float(it.get("importe_neto", 0.0) or 0.0) for it in items)
            iva = sum(float(it.get("importe_iva", 0.0) or 0.0) for it in items)
            total = sum(float(it.get("importe_total", 0.0) or 0.0) for it in items)

            # ---------------- Numeración ----------------
            tipo_comprobante_id = cabecera.get("tipo_comprobante_id")
            pto = cabecera.get("pto_vta")
            numero = cabecera.get("numero")

            if not tipo_comprobante_id:
                raise ValueError("Tipo de comprobante requerido para crear la factura.")
            if not pto:
                raise ValueError("Punto de venta requerido para crear la factura.")

            pto_int = int(pto)

            # Si no vino número desde la UI → usar lógica real (AFIP primero)
            if not numero:
                numero = self._obtener_proximo_numero_real(db, repo, tipo_comprobante_id, pto_int)

            # ---------------- Condición IVA receptor ----------------
            cliente_id = cabecera.get("cliente_id")
            condicion_iva_receptor_id = self._resolver_condicion_iva_receptor(
                db,
                {
                    "cliente_id": cliente_id,
                    "condicion_iva_receptor_id": cabecera.get("condicion_iva_receptor_id"),
                    "condicion_iva_receptor": cabecera.get("condicion_iva_receptor"),
                },
            )

            # ---------------- Estado inicial ----------------
            estado_inicial = self.ESTADO_BORRADOR

            cabecera_db = {
                "tipo_comprobante_id": tipo_comprobante_id,
                "numero": int(numero),
                "fecha_emision": cabecera.get("fecha_emision"),
                "punto_venta": pto_int,
                "moneda": cabecera.get("moneda", "ARS"),
                "cotizacion": float(cabecera.get("cotizacion", 1.0) or 1.0),
                "cae": None,
                "fecha_cae": None,
                "vto_cae": None,
                "subtotal": subtotal,
                "iva": iva,
                "total": total,
                "observaciones": cabecera.get("observaciones"),
                "estado_id": estado_inicial,
                "cliente_id": cliente_id,
                # NUEVO: guardamos el ID de condición IVA del receptor
                "condicion_iva_receptor_id": condicion_iva_receptor_id,
            }

            # ---------------- Insert cabecera ----------------
            # ================== CREAR VENTA BASE ==================
            ventas_service = VentasService()
            
            vehiculo_id = items[0]["vehiculo_id"] if items else None
            cliente_id = cabecera_db.get("cliente_id")
            
            venta_id = ventas_service.crear_venta(
                db=db,  # 👈 MISMA SESIÓN
                cliente_id=cliente_id,
                vehiculo_id=vehiculo_id,
                fecha=cabecera_db.get("fecha_emision"),
            )
            
            
            # ---------------- Insert cabecera ----------------
            cabecera_db["venta_id"] = venta_id
            factura_id = repo.insert_factura(cabecera_db)
            

            db.execute(
                text("""
                    UPDATE facturas
                    SET venta_id = :venta
                    WHERE id = :factura
                """),
                {
                    "venta": venta_id,
                    "factura": factura_id,
                }
            )



            # ---------------- Insert detalle ----------------
            repo.insert_detalle(factura_id, items)
                        # ================== ACTUALIZAR STOCK VEHÍCULOS ==================

            vehiculo_ids = {
                it.get("vehiculo_id")
                for it in items
                if it.get("vehiculo_id")
            }

            if vehiculo_ids:
                # Validar que estén disponibles (estado_stock_id = 1)
                rows = db.execute(
                    text("""
                        SELECT id, estado_stock_id
                        FROM vehiculos
                        WHERE id IN :ids
                    """),
                    {"ids": tuple(vehiculo_ids)},
                ).mappings().all()

                no_disponibles = [
                    r["id"] for r in rows if int(r["estado_stock_id"] or 0) != 1
                ]

                if no_disponibles:
                    raise ValueError(
                        f"Vehículos no disponibles para facturar: {no_disponibles}"
                    )

                # Pasar a VENDIDO (3)
                db.execute(
                    text("""
                        UPDATE vehiculos
                        SET estado_stock_id = :vendido
                        WHERE id IN :ids
                    """),
                    {
                        "vendido": 3,   # Vendido
                        "ids": tuple(vehiculo_ids),
                    }
                )

            # ======================================================


            # ================== COMPLETAR VENTA ==================

            precio_real = float(cabecera.get("precio_real") or 0.0)
            forma_pago_id = cabecera.get("forma_pago_id")
            anticipo = float(cabecera.get("anticipo") or 0.0)
            cantidad_cuotas = int(cabecera.get("cantidad_cuotas") or 0)
            importe_cuota = float(cabecera.get("importe_cuota") or 0.0)


            # Si no es financiación, no pasamos anticipo ni cuotas
            if forma_pago_id != 3:
                anticipo = 0.0
                cantidad_cuotas = 0
                importe_cuota = 0.0

            ventas_service.completar_venta(
                db=db,  # 👈 MISMA sesión
                venta_id=venta_id,
                precio_total=precio_real,
                forma_pago_id=forma_pago_id,
                importe_cuota=importe_cuota,
                anticipo=anticipo,
                cantidad_cuotas=cantidad_cuotas,
                fecha_inicio=cabecera_db.get("fecha_emision"),
            )

            # ======================================================

            db.commit()
            return factura_id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Autorización electrónica en ARCA --------------------

    def autorizar_en_arca(self, factura_id: int) -> Dict[str, Any]:
        """
        Envía la factura indicada al WebService de ARCA / AFIP (WSFEv1)
        para obtener un CAE.

        Siempre devuelve un dict con claves:
        - factura_id, aprobada, rechazada, cae, fecha_cae, vto_cae,
          estado_id, errores, observaciones, mensaje

        Importante:
        - Si la factura queda APROBADA, NO se escriben observaciones
          con textos de ARCA (no ensuciamos el campo).
        - Si hay rechazo o error (respuesta rara / error de comunicación),
          se agrega el detalle a 'observaciones' para poder revisarlo.
        """
        db = SessionLocal()
        factura = None  # para poder usarlo en el except
        try:
            repo = self._repo(db)

            # 1) Leer cabecera
            factura = repo.get_by_id(factura_id)
            logger.debug("Factura {} leída para autorizar", factura_id)

            if not factura:
                raise ValueError(f"Factura {factura_id} no encontrada.")

            # Aseguramos que tenga condición IVA del receptor (por si es vieja)
            condicion_iva_receptor_id = self._resolver_condicion_iva_receptor(
                db,
                factura,
            )
            factura["condicion_iva_receptor_id"] = condicion_iva_receptor_id

            # Si ya tiene CAE y está autorizada, devolvemos eso
            if factura.get("cae") and factura.get("estado_id") == self.ESTADO_AUTORIZADA:
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

            # DEBUG: ver qué dice AFIP sobre el último número antes de pedir CAE
            try:
                fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
                if callable(fe_ult):
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
                    ult_nro = 0
                    if isinstance(ult_raw, dict):
                        for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                            if key in ult_raw and ult_raw[key] is not None:
                                try:
                                    ult_nro = int(ult_raw[key])
                                    break
                                except Exception:
                                    continue
                    else:
                        try:
                            ult_nro = int(ult_raw or 0)
                        except Exception:
                            ult_nro = 0
                    logger.debug(
                        "AFIP último={} espera próximo={} numero_local={}",
                        ult_nro, ult_nro + 1, factura.get("numero"),
                    )
            except Exception as e:
                logger.warning("Error consultando FECompUltimoAutorizado: {}", e)
            # 2) Leer detalle
            items = self._get_detalle_factura(db, factura_id)
            if not items:
                raise ValueError("La factura no tiene ítems en el detalle.")

            # 3) Obtener credenciales (token + sign)
            auth: ArcaAuthData = self._wsaa.get_auth()

            # 4) Llamar a WSFE para solicitar CAE
            try:
                wsfe_result: ArcaWSFEResult = self._wsfe.solicitar_cae(
                    auth=auth,
                    factura=factura,
                    items=items,
                )
            except Exception as e:
                logger.exception("Error al invocar WSFE.solicitar_cae para factura {}", factura_id)
                db.rollback()

                # Guardar el error completo en observaciones (para revisión interna)
                try:
                    self._actualizar_observaciones_factura(
                        db,
                        factura_id=factura_id,
                        mensaje=f"[ARCA] Error de comunicación: {e}",
                    )
                    db.commit()
                except Exception:
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
                    "mensaje": self._clean_error_message(e),
                }

            # 5) Determinar nuevo estado
            if wsfe_result.aprobada:
                nuevo_estado = self.ESTADO_AUTORIZADA
            elif wsfe_result.rechazada:
                nuevo_estado = self.ESTADO_RECHAZADA
            else:
                # WS respondió pero no marcó ni A ni R -> problema de comunicación / formato
                nuevo_estado = self.ESTADO_ERROR_COMUNICACION
            logger.debug("Factura {} → nuevo estado {}", factura_id, nuevo_estado)

            # 6) Actualizar cabecera con CAE / fechas / estado
            repo.actualizar_cae_y_estado(
                factura_id=factura_id,
                cae=wsfe_result.cae,
                fecha_cae=wsfe_result.fecha_cae,
                vto_cae=wsfe_result.vto_cae,
                estado_id=nuevo_estado,
            )
            logger.debug("Factura {} cabecera actualizada con CAE/estado", factura_id)

            # 7) Guardar observaciones SOLO si NO está aprobada
            if not wsfe_result.aprobada:
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

                texto_obs = "\n".join(p for p in partes if p).strip()
                if texto_obs:
                    self._actualizar_observaciones_factura(
                        db,
                        factura_id=factura_id,
                        mensaje=texto_obs,
                    )
            db.commit()
            logger.info("Factura {} autorizada en ARCA. CAE={}", factura_id, wsfe_result.cae)

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
            logger.exception("Error en autorizar_en_arca para factura {}", factura_id)
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
                "mensaje": self._clean_error_message(ex),
            }
        finally:
            db.close()

    # -------------------- Sincronización masiva con ARCA --------------------

    def sincronizar_borradores_con_arca(self) -> Dict[str, Any]:
        """
        Recorre facturas pendientes (BORRADOR / ERROR_COMUNICACION / RECHAZADA / PENDIENTE_AFIP)
        y trata de autorizarlas una por una en ARCA, respetando la numeración real.

        FIX:
        - Si una Nota de Crédito queda AUTORIZADA durante la sincronización,
        se ejecuta el efecto de negocio:
            * anular factura original
            * devolver stock del vehículo
        """
        import time

        resumen = {
            "procesadas": 0,
            "aprobadas": 0,
            "rechazadas": 0,
            "error_comunicacion": 0,
            "detalles": [],
        }

        # 1) Leer facturas pendientes — sesión corta, solo lectura
        with SessionLocal() as db:
            rows = [
                dict(r) for r in db.execute(
                    text(
                        """
                        SELECT id, tipo_comprobante_id, numero, punto_venta
                        FROM facturas
                        WHERE estado_id IN (:est_borr, :est_err, :est_rec, :est_pen)
                        ORDER BY tipo_comprobante_id, punto_venta, numero
                        """
                    ),
                    {
                        "est_borr": self.ESTADO_BORRADOR,
                        "est_err": self.ESTADO_ERROR_COMUNICACION,
                        "est_rec": self.ESTADO_RECHAZADA,
                        "est_pen": self.ESTADO_PENDIENTE_AFIP,
                    },
                ).mappings().all()
            ]

        if not rows:
            return resumen

        # 2) Agrupar en memoria (sin sesión abierta)
        grupos: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        for r in rows:
            key = (r["tipo_comprobante_id"], int(r["punto_venta"]))
            grupos.setdefault(key, []).append(r)

        try:
            auth: ArcaAuthData = self._wsaa.get_auth()
        except Exception as e:
            resumen["detalles"].append(f"No se pudo obtener TA de ARCA: {e}")
            return resumen

        fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)

        for (tipo_comprobante_id, pto_vta), facturas in grupos.items():
            proximo_afip = None

            # 3) Consultar último autorizado en AFIP — sesión corta para lookup de tipo
            if callable(fe_ult):
                try:
                    with SessionLocal() as db:
                        tipo_info = self._repo(db).get_tipo_comprobante_by_id(tipo_comprobante_id)
                    codigo_tipo = str(tipo_info["codigo"]) if tipo_info else str(tipo_comprobante_id)
                    cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(codigo_tipo)
                    ult_raw = fe_ult(auth=auth, cbte_tipo=cbte_tipo, pto_vta=pto_vta)
                    ult_nro = 0
                    if isinstance(ult_raw, dict):
                        for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                            if key in ult_raw and ult_raw[key] is not None:
                                try:
                                    ult_nro = int(ult_raw[key])
                                    break
                                except Exception:
                                    continue
                    else:
                        try:
                            ult_nro = int(ult_raw or 0)
                        except Exception:
                            ult_nro = 0
                    proximo_afip = ult_nro + 1
                except Exception as e:
                    resumen["detalles"].append(
                        f"[{tipo_comprobante_id} {pto_vta}] Error al consultar FECompUltimoAutorizado: {e}"
                    )

            # 4) Fallback local
            if proximo_afip is None:
                proximo_afip = max((int(f.get("numero") or 0) for f in facturas), default=0) + 1

            # 5) Procesar cada factura del grupo
            for f in facturas:
                factura_id = f["id"]
                num_local = int(f.get("numero") or 0)

                # Ajustar numeración si hace falta — sesión corta, commit inmediato
                if num_local != proximo_afip:
                    with SessionLocal() as db:
                        db.execute(
                            text("UPDATE facturas SET numero = :num WHERE id = :id"),
                            {"num": proximo_afip, "id": factura_id},
                        )
                        db.commit()
                    f["numero"] = proximo_afip
                    num_local = proximo_afip

                # Pausa entre calls a AFIP para respetar el límite de requests
                time.sleep(0.2)

                # Autorizar — tiene su propia sesión interna
                res = self.autorizar_en_arca(factura_id)
                resumen["procesadas"] += 1

                if res.get("aprobada"):
                    resumen["aprobadas"] += 1
                    resumen["detalles"].append(
                        f"Factura {factura_id} [{tipo_comprobante_id} {str(pto_vta).zfill(4)}-{num_local}] APROBADA."
                    )
                    # Efectos NC — sesión corta, commit propio
                    with SessionLocal() as db:
                        self._procesar_nc_autorizada(db, factura_id)
                        db.commit()
                    proximo_afip += 1

                elif res.get("rechazada"):
                    resumen["rechazadas"] += 1
                    resumen["detalles"].append(
                        f"Factura {factura_id} [{tipo_comprobante_id} {str(pto_vta).zfill(4)}-{num_local}] "
                        f"RECHAZADA: {res.get('mensaje')}"
                    )
                    proximo_afip += 1

                else:
                    resumen["error_comunicacion"] += 1
                    resumen["detalles"].append(
                        f"Factura {factura_id} [{tipo_comprobante_id} {str(pto_vta).zfill(4)}-{num_local}] "
                        f"ERROR COMUNICACIÓN: {res.get('mensaje')}"
                    )

        return resumen

    def _procesar_nc_autorizada(self, db: Session, nc_id: int) -> None:
        """
        Lógica de negocio cuando una Nota de Crédito queda AUTORIZADA:

        - Anula factura original
        - Devuelve stock del vehículo
        - Cancela la venta asociada
        - Marca cuotas como ANULADAS (aunque tengan pagos)
        """

        repo = self._repo(db)
        nc = repo.get_by_id(nc_id)

        if not nc:
            return

        # Solo aplica si es Nota de Crédito
        tipo = repo.get_tipo_comprobante_by_id(nc["tipo_comprobante_id"])
        if not tipo or not tipo.get("es_nota_credito"):
            return

        factura_origen_id = nc.get("factura_origen_id")
        if not factura_origen_id:
            return

        factura_original = repo.get_by_id(factura_origen_id)
        if not factura_original:
            return

        # ---------------------------------------------------
        # 1️⃣ Anular factura original
        # ---------------------------------------------------
        repo.actualizar_estado(
            factura_origen_id,
            self.ESTADO_ANULADA_POR_NC
        )

        # ---------------------------------------------------
        # 2️⃣ Devolver stock del vehículo
        # ---------------------------------------------------
        db.execute(
            text("""
                UPDATE vehiculos
                SET estado_stock_id = 1  -- Disponible
                WHERE id IN (
                    SELECT fd.vehiculo_id
                    FROM facturas_detalle fd
                    WHERE fd.factura_id = :factura_orig_id
                    AND fd.vehiculo_id IS NOT NULL
                )
            """),
            {"factura_orig_id": factura_origen_id}
        )

        # ---------------------------------------------------
        # 3️⃣ Cancelar venta asociada
        # ---------------------------------------------------
        venta_id = factura_original.get("venta_id")
        if not venta_id:
            return

        db.execute(
            text("""
                UPDATE ventas
                SET estado_id = :estado_cancelada
                WHERE id = :venta_id
            """),
            {"estado_cancelada": self.ESTADO_VENTA_CANCELADA, "venta_id": venta_id}
        )

        # ---------------------------------------------------
        # 4️⃣ Buscar plan de financiación
        # ---------------------------------------------------
        plan = db.execute(
            text("""
                SELECT id
                FROM plan_financiacion
                WHERE venta_id = :venta_id
            """),
            {"venta_id": venta_id}
        ).mappings().first()

        if not plan:
            return

        plan_id = plan["id"]

        # ---------------------------------------------------
        # 5️⃣ Anular TODAS las cuotas (aunque tengan pagos)
        # ---------------------------------------------------
        db.execute(
            text("""
                UPDATE cuotas
                SET estado = 'ANULADA'
                WHERE plan_id = :plan_id
            """),
            {"plan_id": plan_id}
        )



    # -------------------- Nota de crédito --------------------
    def generar_nota_credito(self, factura_id: int) -> Dict[str, Any]:
        """
        Genera una Nota de Crédito que anula la factura indicada.
        """

        db = SessionLocal()

        try:
            repo = self._repo(db)

            factura_original = repo.get_by_id(factura_id)
            if not factura_original:
                raise ValueError(f"Factura {factura_id} no encontrada.")

            items_original = repo.get_detalle_by_factura(factura_id)
            if not items_original:
                raise ValueError("La factura original no tiene ítems.")

            # ---------------------------------------------------
            # Tipo original
            # ---------------------------------------------------
            tipo_orig = repo.get_tipo_comprobante_by_id(
                factura_original["tipo_comprobante_id"]
            )

            if not tipo_orig:
                raise ValueError("Tipo comprobante original no encontrado.")

            pto_vta = factura_original.get("punto_venta")

            # ---------------------------------------------------
            # Buscar tipo NC correspondiente
            # ---------------------------------------------------
            tipo_nc = repo.get_tipo_nota_credito_por_letra(tipo_orig["letra"])

            if not tipo_nc:
                raise ValueError("No se encontró tipo de Nota de Crédito correspondiente.")

            tipo_nc_id = tipo_nc["id"]
            tipo_nc_codigo = tipo_nc["codigo"]

            # ---------------------------------------------------
            # Obtener último autorizado en AFIP
            # ---------------------------------------------------
            ultimo_autorizado = 0

            try:
                fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)
                if callable(fe_ult):
                    auth: ArcaAuthData = self._wsaa.get_auth()

                    cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(
                        tipo_nc_codigo
                    )

                    ult_raw = fe_ult(
                        auth=auth,
                        cbte_tipo=cbte_tipo,
                        pto_vta=int(pto_vta),
                    )

                    if isinstance(ult_raw, dict):
                        for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                            if key in ult_raw and ult_raw[key] is not None:
                                ultimo_autorizado = int(ult_raw[key])
                                break
                    else:
                        ultimo_autorizado = int(ult_raw or 0)

            except Exception:
                ultimo_autorizado = 0

            numero_nc = ultimo_autorizado + 1

            # ---------------------------------------------------
            # Generar items negativos
            # ---------------------------------------------------
            items_nc: List[Dict[str, Any]] = []
            subtotal_nc = 0.0
            iva_nc = 0.0
            total_nc = 0.0

            for it in items_original:
                cantidad = float(it.get("cantidad") or 0.0)
                precio_unit = float(it.get("precio_unitario") or 0.0)
                alic_iva = float(it.get("alicuota_iva") or 0.0)

                neto_orig = float(it.get("importe_neto") or 0.0)
                iva_orig = float(it.get("importe_iva") or 0.0)
                total_orig = float(it.get("importe_total") or 0.0)

                neto_nc = -abs(neto_orig)
                iva_nc_item = -abs(iva_orig)
                total_nc_item = -abs(total_orig)

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

            hoy = date.today().strftime("%Y-%m-%d")

            observ = (
                f"NC que anula factura {tipo_orig['codigo']} "
                f"{str(pto_vta).zfill(4)}-{factura_original.get('numero')}"
            )

            condicion_iva_nc_id = self._resolver_condicion_iva_receptor(
                db,
                factura_original,
            )

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
                "estado_id": self.ESTADO_BORRADOR,
                "cliente_id": factura_original.get("cliente_id"),
                "condicion_iva_receptor_id": condicion_iva_nc_id,
                "cbte_asoc_tipo": tipo_orig["codigo"],   # ✅ FIX
                "cbte_asoc_pto_vta": int(pto_vta),
                "cbte_asoc_numero": factura_original.get("numero"),
                "factura_origen_id": factura_id,
            }

            nc_id = repo.insert_factura(cabecera_nc)
            repo.insert_detalle(nc_id, items_nc)

            # ---------------------------------------------------
            # Solicitar CAE
            # ---------------------------------------------------
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
                estado_nc = self.ESTADO_AUTORIZADA
            elif wsfe_result.rechazada:
                estado_nc = self.ESTADO_RECHAZADA
            else:
                estado_nc = self.ESTADO_ERROR_COMUNICACION

            repo.actualizar_cae_y_estado(
                factura_id=nc_id,
                cae=wsfe_result.cae,
                fecha_cae=wsfe_result.fecha_cae,
                vto_cae=wsfe_result.vto_cae,
                estado_id=estado_nc,
            )

            if wsfe_result.aprobada:
                self._procesar_nc_autorizada(db, nc_id)

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

                # 👇 ESTO ES LO QUE TE FALTA
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

    def consultar_comprobante_arca(
        self,
        tipo_comprobante_id: str,
        pto_vta: int,
        numero: int,
    ) -> Dict[str, Any]:
        """
        Consulta un comprobante en AFIP/ARCA usando FECompConsultar
        y devuelve datos normalizados para la UI.
        """
        auth: ArcaAuthData = self._wsaa.get_auth()
        cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(tipo_comprobante_id)

        fe_cons = getattr(self._wsfe, "fe_comp_consultar", None)
        if not callable(fe_cons):
            raise RuntimeError("WSFE no implementa FECompConsultar")

        raw = fe_cons(
            auth=auth,
            cbte_tipo=cbte_tipo,
            pto_vta=int(pto_vta),
            cbte_nro=int(numero),
        )

        return {
            "estado": raw.get("resultado"),
            "cae": raw.get("cae"),
            "fecha_cae": raw.get("fecha_cae"),
            "vto_cae": raw.get("vto_cae"),
            "importe_total": raw.get("imp_total"),
            "errores": raw.get("errores") or [],
            "observaciones": raw.get("observaciones") or [],
        }

    def get_codigo_tipo(self, tipo_id: int) -> Optional[str]:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.get_codigo_tipo_comprobante(tipo_id)
        finally:
            db.close()

    # -------------------- Método viejo (no se toca) --------------------

    def create_factura(self, data: Dict[str, Any]) -> int:
        """
        Crea una factura y devuelve su ID.
        Para compatibilidad con código antiguo.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            payload = dict(data)

            for k in ("cliente_id", "estado_id", "pto_vta", "numero", "total"):
                if payload.get(k) in ("", " ", None):
                    payload[k] = None

            fn = getattr(repo, "create_factura", None)
            if not callable(fn):
                raise AttributeError(
                    "FacturasRepository no implementa un método create_factura compatible."
                )

            new_id = fn(payload)
            if not new_id:
                new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            db.commit()
            return int(new_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Utilidades --------------------

    def warmup_catalogos(self) -> None:
        self._catalogos.warmup_all()

    def _catalogos_get_value_safe(self, key: str):
        try:
            cache = self._catalogos
            if hasattr(cache, "get_value"):
                return cache.get_value(key)
            if hasattr(cache, "get"):
                return cache.get(key)
        except Exception:
            return None

    # -------- Helpers internos ARCA --------

    def _get_detalle_factura(self, db: Session, factura_id: int) -> List[Dict[str, Any]]:
        """
        Wrapper interno para obtener detalle usando el repository.
        """
        repo = self._repo(db)
        return repo.get_detalle_by_factura(factura_id)

    def _actualizar_observaciones_factura(
        self,
        db: Session,
        factura_id: int,
        mensaje: str,
    ) -> None:
        """
        Agrega (append) texto a las observaciones de la factura.
        No pisa lo que ya hubiera, sólo suma en una nueva línea.
        """
        if not mensaje:
            return

        db.execute(
            text(
                """
                UPDATE facturas
                SET observaciones = TRIM(
                    CONCAT(
                        COALESCE(observaciones, ''),



                        CASE
                            WHEN observaciones IS NULL OR observaciones = '' THEN ''
                            ELSE '\n'
                        END,
                        :obs
                    )
                )
                WHERE id = :id
                """
            ),
            {"id": factura_id, "obs": mensaje},
        )

    # -------- Condición IVA receptor (núcleo) --------

    def _resolver_condicion_iva_receptor(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Optional[int]:
        """
        Determina el ID de condición frente al IVA del receptor (INT).

        Prioridad:
        1) data["condicion_iva_receptor_id"] si viene.
        2) data["condicion_iva_receptor"] si viene como código o nombre
           (ej: "CF", "RI", "Consumidor Final", etc.), mapeado a ID.
        3) Deducción por tipo_doc del cliente (DNI -> CF, CUIT -> RI -> luego map a ID).
        """

        if not data:
            return None

        # 1) Ya viene el ID directamente
        raw_id = data.get("condicion_iva_receptor_id")
        if raw_id not in (None, "", "0", 0):
            try:
                return int(raw_id)
            except Exception:
                pass

        # 2) Viene un código / texto (CF, RI, "Consumidor Final", etc.)
        raw_code = data.get("condicion_iva_receptor")
        mapped = self._map_condicion_iva_code_to_id(raw_code)
        if mapped is not None:
            return mapped

        # 3) Deducción por tipo_doc de cliente (ya sin usar columna de clientes.condicion_iva_receptor)
        cliente_id = data.get("cliente_id")
        if not cliente_id:
            return None

        tipo_doc = None
        try:
            row = db.execute(
                text(
                    """
                    SELECT tipo_doc_id
                    FROM clientes
                    WHERE id = :id
                    """
                ),
                {"id": cliente_id},
            ).mappings().first()

            if row:
                tipo_doc_id = row.get("tipo_doc_id")
            else:
                tipo_doc_id = None

        except Exception:
            tipo_doc = None

        default_code = None
        # AFIP:
        # 96 = DNI → Consumidor Final
        # 80 = CUIT → Responsable Inscripto

        # Resolver desde catálogo de tipos_documento (sin IDs mágicos)
        tipo_doc = self._catalogos.get_tipo_doc_by_id(tipo_doc_id)

        default_code = None

        if tipo_doc:
            codigo = (tipo_doc.get("codigo") or "").upper()

            if codigo == "DNI":
                default_code = "CF"   # Consumidor Final
            elif codigo in ("CUIT", "CUIL"):
                default_code = "RI"   # Responsable Inscripto



        if default_code:
            return self._map_condicion_iva_code_to_id(default_code)

        return None

    def _map_condicion_iva_code_to_id(self, value: Any) -> Optional[int]:
        """
        Mapea un código / nombre de condición IVA a su ID (según la lista configurada).

        Acepta:
        - "CF", "RI", "EX", "MT"
        - Nombre/descripción (p.ej. "Consumidor Final", "IVA Responsable Inscripto")
        - Un string numérico -> se trata como ID directo.
        """
        if value in (None, "", 0, "0"):
            return None

        # Si ya parece un número, lo intentamos directo.
        try:
            as_int = int(str(value))
            if as_int > 0:
                return as_int
        except Exception:
            pass

        txt = str(value).strip().upper()
        if not txt:
            return None

        condiciones = self.get_condiciones_iva_receptor()
        for c in condiciones:
            cid = c.get("id")
            try:
                cid_int = int(cid)
            except Exception:
                continue

            codigo = str(c.get("codigo") or "").strip().upper()
            nombre = str(c.get("nombre") or "").strip().upper()
            desc = str(c.get("descripcion") or "").strip().upper()

            if txt == codigo or txt == nombre or txt == desc:
                return cid_int

        return None
