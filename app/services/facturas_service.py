from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from loguru import logger

from app.core.config import settings
from app.data.database import SessionLocal
from app.repositories.facturas_repository import FacturasRepository
from app.services.catalogos_service import CatalogosService
from app.services.arca_authorization_service import ArcaAuthorizationService
from app.services.audit_log_service import AuditLogService
from app.services.factura_numbering_service import FacturaNumberingService
from app.services.factura_rejection_service import FacturaRejectionService
from app.services.nota_credito_creator import NotaCreditoCreator
from app.services.nota_credito_service import NotaCreditoService
from app.services.stock_service import StockService
from app.services.venta_creator import VentaCreator

# Integraciones ARCA / AFIP
from app.integrations.arca.wsaa_client import ArcaWSAAClient, ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient

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
        self._audit = AuditLogService()
        self._stock = StockService()
        self._venta_creator = VentaCreator(stock_service=self._stock)
        self._nota_credito = NotaCreditoService(
            repo_factory=self._repo,
            stock_service=self._stock,
            estado_anulada_por_nc_getter=lambda: self.ESTADO_ANULADA_POR_NC,
            estado_venta_cancelada_getter=lambda: self.ESTADO_VENTA_CANCELADA,
        )
        self._factura_rejection = FacturaRejectionService(
            repo_factory=self._repo,
            stock_service=self._stock,
            estado_venta_cancelada_getter=lambda: self.ESTADO_VENTA_CANCELADA,
            audit=self._audit,
        )

        # Clientes de integración con ARCA
        # wsaa -> autenticación (token + sign)
        # wsfe -> facturación electrónica (CAE)
        self._wsaa = ArcaWSAAClient()
        self._wsfe = ArcaWSFEClient()
        self._numbering = FacturaNumberingService(
            wsaa=self._wsaa,
            wsfe=self._wsfe,
            repo_factory=self._repo,
        )
        self._arca_authorization = ArcaAuthorizationService(
            wsaa=self._wsaa,
            wsfe=self._wsfe,
            repo_factory=self._repo,
            detalle_getter=self._get_detalle_factura,
            condicion_resolver=self._resolver_condicion_iva_receptor,
            observaciones_updater=self._actualizar_observaciones_factura,
            error_cleaner=self._clean_error_message,
            estado_autorizada_getter=lambda: self.ESTADO_AUTORIZADA,
            estado_rechazada_getter=lambda: self.ESTADO_RECHAZADA,
            estado_error_getter=lambda: self.ESTADO_ERROR_COMUNICACION,
            rejected_effects_processor=self._factura_rejection.procesar_rechazo,
        )
        self._nota_credito_creator = NotaCreditoCreator(
            wsaa=self._wsaa,
            wsfe=self._wsfe,
            repo_factory=self._repo,
            condicion_resolver=self._resolver_condicion_iva_receptor,
            nc_effects_processor=self._nota_credito.procesar_nc_autorizada,
            estado_borrador_getter=lambda: self.ESTADO_BORRADOR,
            estado_autorizada_getter=lambda: self.ESTADO_AUTORIZADA,
            estado_rechazada_getter=lambda: self.ESTADO_RECHAZADA,
            estado_error_getter=lambda: self.ESTADO_ERROR_COMUNICACION,
            audit=self._audit,
        )

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
        estados = self._catalogos_get_value_safe("estados_facturas")
        if estados:
            return estados

        db = SessionLocal()
        try:
            estados = self._repo(db).list_estados_facturas()
            try:
                if hasattr(self._catalogos, "set"):
                    self._catalogos.set("estados_facturas", estados)
            except Exception:
                pass
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

            conflicto_numero = db.execute(
                text(
                    """
                    SELECT id, estado_id, cae
                    FROM facturas
                    WHERE tipo_comprobante_id = :tipo
                      AND punto_venta = :pto
                      AND numero = :numero
                    LIMIT 1
                    """
                ),
                {
                    "tipo": tipo_comprobante_id,
                    "pto": pto_int,
                    "numero": int(numero),
                },
            ).mappings().first()

            if conflicto_numero:
                raise ValueError(
                    "No se puede crear la factura porque el número "
                    f"{pto_int}-{int(numero):08d} ya existe en la base local "
                    f"(factura id {conflicto_numero['id']}). "
                    f"ARCA {settings.ARCA_ENV} informa ese número como próximo, "
                    "pero la base de desarrollo fue clonada con comprobantes previos. "
                    "Para probar homologación sin tocar datos existentes hace falta usar "
                    "una base de pruebas sin facturas de ese punto/tipo, o separar la "
                    "numeración local por ambiente."
                )

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
            venta_id = self._venta_creator.crear_venta_base(
                db=db,
                cabecera_db=cabecera_db,
                items=items,
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
            self._venta_creator.marcar_vehiculos_vendidos(
                db=db,
                factura_id=factura_id,
                items=items,
            )

            self._venta_creator.completar_venta_desde_factura(
                db=db,
                venta_id=venta_id,
                cabecera=cabecera,
                cabecera_db=cabecera_db,
            )

            self._audit.registrar(
                db,
                entidad="facturas",
                entidad_id=factura_id,
                accion="FACTURA_CREADA",
                datos_nuevos={
                    "venta_id": venta_id,
                    "cliente_id": cabecera_db.get("cliente_id"),
                    "tipo_comprobante_id": cabecera_db.get("tipo_comprobante_id"),
                    "numero": cabecera_db.get("numero"),
                    "punto_venta": cabecera_db.get("punto_venta"),
                    "total": cabecera_db.get("total"),
                },
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

    # ------------------------------------------------------------------
    # Etapa 5: delegaciones temporales hacia FacturaNumberingService.
    # Los bloques antiguos quedan arriba hasta completar limpieza segura.
    # ------------------------------------------------------------------
    def autorizar_en_arca(self, factura_id: int) -> Dict[str, Any]:
        return self._arca_authorization.autorizar_factura(factura_id)

    def generar_nota_credito(self, factura_id: int) -> Dict[str, Any]:
        return self._nota_credito_creator.generar_nota_credito(factura_id)

    def sugerir_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> int:
        return self._numbering.sugerir_proximo_numero(tipo_comprobante_id, pto_vta)

    def diagnosticar_proximo_numero(self, tipo_comprobante_id: str, pto_vta: Any) -> Dict[str, Any]:
        return self._numbering.diagnosticar_proximo_numero(tipo_comprobante_id, pto_vta)

    def _obtener_proximo_numero_real(
        self,
        db: Session,
        repo: FacturasRepository,
        tipo_comprobante_id: int,
        pto_vta: int,
    ) -> int:
        return self._numbering.obtener_proximo_numero_real(
            db,
            repo,
            tipo_comprobante_id,
            pto_vta,
        )

    def _procesar_nc_autorizada(self, db: Session, nc_id: int) -> None:
        self._nota_credito.procesar_nc_autorizada(db, nc_id)
