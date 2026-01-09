from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.facturas_repository import FacturasRepository
from app.services.catalogos_service import CatalogosService

# Integraciones ARCA / AFIP
from app.integrations.arca.wsaa_client import ArcaWSAAClient, ArcaAuthData
from app.integrations.arca.wsfe_client import ArcaWSFEClient, ArcaWSFEResult


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

    def _init_estado_ids(self) -> None:
        """Intenta resolver IDs de estados por nombre desde la BD.

        Esto evita errores cuando los IDs cambian entre instalaciones.
        Si la tabla/consulta falla, se mantienen los valores por defecto.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            estados = repo.list_estados_facturas() or []
            por_nombre = {str(e.get("nombre", "")).strip().lower(): int(e.get("id")) for e in estados if e.get("id") is not None}

            def pick(*names: str) -> Optional[int]:
                for n in names:
                    k = str(n).strip().lower()
                    if k in por_nombre:
                        return por_nombre[k]
                return None

            self.ESTADO_ANULADA = pick("Anulada") or self.ESTADO_ANULADA
            self.ESTADO_ANULADA_POR_NC = pick("Anulada por NC", "Anulada por N/C", "Anulada") or self.ESTADO_ANULADA_POR_NC
        except Exception:
            # No interrumpimos el inicio por un problema de catálogos
            pass
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

    def sugerir_proximo_numero(self, tipo: str, pto_vta: Any) -> int:
        """
        Devuelve el próximo número de factura según tipo y punto de venta.

        Ahora:
        - Intenta primero con AFIP (FECompUltimoAutorizado).
        - SOLO si AFIP falla (error de WS), cae a la BD.
        """
        print(">>> [sugerir_proximo_numero] tipo =", tipo, "pto_vta =", pto_vta)

        if not tipo or not pto_vta:
            print(">>>   faltan datos, devuelvo 1")
            return 1

        try:
            pto = int(pto_vta)
        except Exception:
            pto = 1

        db = SessionLocal()
        try:
            repo = self._repo(db)
            nro = self._obtener_proximo_numero_real(db, repo, tipo, pto)
            print(">>> [sugerir_proximo_numero] numero sugerido =", nro)
            return nro
        finally:
            db.close()

    def diagnosticar_proximo_numero(self, tipo: str, pto_vta: Any) -> Dict[str, Any]:
        """
        Versión 'verbose' de la numeración para usar en la pantalla
        de Configuración ARCA.

        Devuelve un dict con:
          - tipo, pto_vta
          - proximo: int
          - origen: 'AFIP' | 'BD'
          - ws_ok: bool
          - ultimo_afip: Optional[int]
          - proximo_local: Optional[int]
          - errores: List[str]
          - mensaje: str
        """
        info: Dict[str, Any] = {
            "tipo": tipo,
            "pto_vta": None,
            "proximo": 1,
            "origen": "BD",
            "ws_ok": False,
            "ultimo_afip": None,
            "proximo_local": None,
            "errores": [],
            "mensaje": "",
        }

        if not tipo or not pto_vta:
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
                    cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(tipo)

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
                    proximo_local = repo.get_next_numero(tipo, pto)
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
                proximo_local = repo.get_next_numero(tipo, pto)
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
        tipo: str,
        pto_vta: int,
    ) -> int:
        """
        Calcula el próximo número de comprobante.

        PRIORIDAD AHORA:
        1) AFIP (FECompUltimoAutorizado)  -> (ultimo_afip o 0) + 1
           *Se usa SIEMPRE si el WS responde OK, aunque el último sea 0.*
        2) Si AFIP falla (error de WS): BD (repo.get_next_numero)
        """
        print(">>> [_obtener_proximo_numero_real] INICIO tipo =", tipo, "pto_vta =", pto_vta)

        # 1) Intentar AFIP primero
        ultimo_afip: Optional[int] = None
        ws_llamado_ok = False

        fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)

        if callable(fe_ult):
            try:
                # Auth ARCA
                auth: ArcaAuthData = self._wsaa.get_auth()
                print(">>>   [AFIP] TA OK, vence:", auth.expires_at)

                cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(tipo)
                print(
                    f">>>   [AFIP] Llamando FECompUltimoAutorizado(cbte_tipo={cbte_tipo}, "
                    f"pto_vta={pto_vta})"
                )

                ultimo_afip_raw = fe_ult(
                    auth=auth,
                    cbte_tipo=cbte_tipo,
                    pto_vta=pto_vta,
                )
                ws_llamado_ok = True
                print(">>>   [AFIP] Respuesta FECompUltimoAutorizado RAW =", ultimo_afip_raw)

                # Puede venir int o dict, lo tratamos defensivo
                if isinstance(ultimo_afip_raw, dict):
                    for key in ("cbte_nro", "numero", "CbteNro", "cbtenro"):
                        if key in ultimo_afip_raw and ultimo_afip_raw[key] is not None:
                            try:
                                ultimo_afip = int(ultimo_afip_raw[key])
                                print(">>>   [AFIP] ultimo_afip (dict)", key, "=", ultimo_afip)
                                break
                            except Exception as e:
                                print(">>>   [AFIP] ERROR parseando", key, ":", repr(e))
                else:
                    try:
                        ultimo_afip = int(ultimo_afip_raw or 0)
                        print(">>>   [AFIP] ultimo_afip (directo) =", ultimo_afip)
                    except Exception as e:
                        print(">>>   [AFIP] ERROR parseando ultimo_afip_raw directo:", repr(e))
                        ultimo_afip = None

            except Exception as e:
                print(">>>   [AFIP] ERROR al llamar FECompUltimoAutorizado:", repr(e))
                ws_llamado_ok = False
                ultimo_afip = None
        else:
            print(">>>   [AFIP] self._wsfe NO tiene fe_comp_ultimo_autorizado")

        # Si el WS respondió OK, usamos SIEMPRE lo que diga AFIP
        if ws_llamado_ok:
            if ultimo_afip is None:
                ultimo_afip = 0
            proximo = ultimo_afip + 1
            print(
                f">>>   [AFIP] ultimo_afip={ultimo_afip} => próximo a usar desde WS="
                f"{proximo}"
            )
            return proximo

        print(">>>   [LOCAL] No se pudo usar AFIP (WS falló), voy a BD...")

        # 2) Fallback: lo que tengas en BD
        proximo_local = 1
        try:
            proximo_local = repo.get_next_numero(tipo, pto_vta)  # normalmente last_local + 1
            print(">>>   [LOCAL] repo.get_next_numero(tipo, pto_vta) devolvió =", proximo_local)
        except Exception as e:
            print(">>>   [LOCAL] ERROR en repo.get_next_numero:", repr(e))
            proximo_local = 1

        if not proximo_local or proximo_local <= 0:
            proximo_local = 1

        print(">>>   [LOCAL] Usando BD: próximo =", proximo_local)
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
        Devuelve solo la cabecera de factura (+ datos de cliente/estado).
        Usado para la pantalla de consulta.
        """
        db = SessionLocal()
        try:
            return self._repo(db).get_by_id(factura_id)
        finally:
            db.close()

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
            tipo = cabecera.get("tipo")
            pto = cabecera.get("pto_vta")
            numero = cabecera.get("numero")

            if not tipo:
                raise ValueError("Tipo de comprobante requerido para crear la factura.")
            if not pto:
                raise ValueError("Punto de venta requerido para crear la factura.")

            pto_int = int(pto)

            # Si no vino número desde la UI → usar lógica real (AFIP primero)
            if not numero:
                numero = self._obtener_proximo_numero_real(db, repo, tipo, pto_int)

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
                "tipo": tipo,
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
            factura_id = repo.insert_factura(cabecera_db)

            # ---------------- Insert detalle ----------------
            repo.insert_detalle(factura_id, items)

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
        print("hola autorizar arca")
        db = SessionLocal()
        factura = None  # para poder usarlo en el except
        try:
            repo = self._repo(db)

            # 1) Leer cabecera
            factura = repo.get_by_id(factura_id)
            print("Factura leída en autorizar_en_arca:", factura)

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
                    cbte_tipo_dbg = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(
                        factura.get("tipo")
                    )
                    pto_dbg = int(factura.get("punto_venta") or 0)
                    ult_raw = fe_ult(
                        auth=auth_debug,
                        cbte_tipo=cbte_tipo_dbg,
                        pto_vta=pto_dbg,
                    )
                    print(
                        ">>> [autorizar_en_arca][DEBUG] FECompUltimoAutorizado RAW =", ult_raw
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
                    esperado = ult_nro + 1
                    print(
                        ">>> [autorizar_en_arca][DEBUG] AFIP último =",
                        ult_nro,
                        "espera próximo =",
                        esperado,
                        "numero_local =",
                        factura.get("numero"),
                    )
                else:
                    print(
                        ">>> [autorizar_en_arca][DEBUG] self._wsfe no tiene "
                        "fe_comp_ultimo_autorizado"
                    )
            except Exception as e:
                print(
                    ">>> [autorizar_en_arca][DEBUG] Error consultando FECompUltimoAutorizado:",
                    repr(e),
                )

            print("1")
            # 2) Leer detalle
            items = self._get_detalle_factura(db, factura_id)
            if not items:
                raise ValueError("La factura no tiene ítems en el detalle.")
            print("2")

            # 3) Obtener credenciales (token + sign)
            auth: ArcaAuthData = self._wsaa.get_auth()
            print("3 - auth obtenido, vence:", auth.expires_at)

            # Debug rápido
            print("Auth:", auth)
            print("Factura:", factura)
            print("Items:", items)

            # 4) Llamar a WSFE para solicitar CAE
            from pprint import pformat
            try:
                print("4 - llamando a WSFE.solicitar_cae...")
                wsfe_result: ArcaWSFEResult = self._wsfe.solicitar_cae(
                    auth=auth,
                    factura=factura,
                    items=items,
                )
                print("5 - WSFE respondió:", wsfe_result)
            except Exception as e:
                import traceback
                print("ERROR al llamar a WSFE.solicitar_cae:", repr(e))
                traceback.print_exc()
                db.rollback()

                # Guardar el error en observaciones (sin tocar estado)
                try:
                    self._actualizar_observaciones_factura(
                        db,
                        factura_id=factura_id,
                        mensaje=f"[ARCA] Error al invocar WSFE.solicitar_cae: {e}",
                    )
                    db.commit()
                except Exception as ex2:
                    print("ERROR al guardar observaciones de error ARCA:", repr(ex2))
                    db.rollback()

                # Devolvemos algo entendible para la UI; NO cambiamos estado
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
                    "mensaje": f"Error al invocar WSFE.solicitar_cae: {e}",
                }

            # 5) Determinar nuevo estado
            if wsfe_result.aprobada:
                nuevo_estado = self.ESTADO_AUTORIZADA
            elif wsfe_result.rechazada:
                nuevo_estado = self.ESTADO_RECHAZADA
            else:
                # WS respondió pero no marcó ni A ni R -> problema de comunicación / formato
                nuevo_estado = self.ESTADO_ERROR_COMUNICACION
            print("6 - nuevo estado:", nuevo_estado)

            # 6) Actualizar cabecera con CAE / fechas / estado
            repo.actualizar_cae_y_estado(
                factura_id=factura_id,
                cae=wsfe_result.cae,
                fecha_cae=wsfe_result.fecha_cae,
                vto_cae=wsfe_result.vto_cae,
                estado_id=nuevo_estado,
            )
            print("7 - cabecera actualizada con CAE/estado")

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
            print("8 - observaciones actualizadas (solo si había error / rechazo)")

            db.commit()
            print("9 - commit OK en autorizar_en_arca")

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
            import traceback
            print("ERROR general en autorizar_en_arca:", repr(ex))
            traceback.print_exc()
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
                "mensaje": f"Error interno en autorizar_en_arca: {ex}",
            }
        finally:
            db.close()

    # -------------------- Sincronización masiva con ARCA --------------------

    def sincronizar_borradores_con_arca(self) -> Dict[str, Any]:
        """
        Recorre facturas pendientes (BORRADOR / ERROR_COMUNICACION) y trata de
        autorizarlas una por una en ARCA, respetando la numeración real.
        """
        db = SessionLocal()
        resumen = {
            "procesadas": 0,
            "aprobadas": 0,
            "rechazadas": 0,
            "error_comunicacion": 0,
            "detalles": [],
        }
        try:
            rows = db.execute(
                text(
                    """
                    SELECT id, tipo, numero, punto_venta
                    FROM facturas
                    WHERE estado_id IN (:est_borr, :est_err, :est_rec, :est_pen)
                    ORDER BY tipo, punto_venta, numero
                    """
                ),
                {
                    "est_borr": self.ESTADO_BORRADOR,
                    "est_err": self.ESTADO_ERROR_COMUNICACION,
                    "est_rec": self.ESTADO_RECHAZADA,
                    "est_pen": self.ESTADO_PENDIENTE_AFIP,
                },
            ).mappings().all()

            if not rows:
                return resumen

            grupos: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
            for r in rows:
                key = (r["tipo"], int(r["punto_venta"]))
                grupos.setdefault(key, []).append(dict(r))

            try:
                auth: ArcaAuthData = self._wsaa.get_auth()
            except Exception as e:
                resumen["detalles"].append(f"No se pudo obtener TA de ARCA: {e}")
                return resumen

            fe_ult = getattr(self._wsfe, "fe_comp_ultimo_autorizado", None)

            for (tipo, pto_vta), facturas in grupos.items():
                proximo_afip = None
                if callable(fe_ult):
                    try:
                        cbte_tipo = ArcaWSFEClient._map_tipo_comprobante_to_afip_code(tipo)
                        ult_raw = fe_ult(
                            auth=auth,
                            cbte_tipo=cbte_tipo,
                            pto_vta=pto_vta,
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
                        proximo_afip = ult_nro + 1
                    except Exception as e:
                        resumen["detalles"].append(
                            f"[{tipo} {pto_vta}] Error al consultar FECompUltimoAutorizado: {e}"
                        )

                if proximo_afip is None:
                    max_local = 0
                    for f in facturas:
                        try:
                            n = int(f.get("numero") or 0)
                            if n > max_local:
                                max_local = n
                        except Exception:
                            continue
                    proximo_afip = max_local + 1

                for f in facturas:
                    factura_id = f["id"]
                    num_local = int(f.get("numero") or 0)

                    if num_local != proximo_afip:
                        db.execute(
                            text("UPDATE facturas SET numero = :num WHERE id = :id"),
                            {"num": proximo_afip, "id": factura_id},
                        )
                        f["numero"] = proximo_afip
                        num_local = proximo_afip

                    res = self.autorizar_en_arca(factura_id)

                    resumen["procesadas"] += 1

                    if res.get("aprobada"):
                        resumen["aprobadas"] += 1
                        resumen["detalles"].append(
                            f"Factura {factura_id} [{tipo} {str(pto_vta).zfill(4)}-{num_local}] APROBADA."
                        )
                        proximo_afip += 1
                    elif res.get("rechazada"):
                        resumen["rechazadas"] += 1
                        resumen["detalles"].append(
                            f"Factura {factura_id} [{tipo} {str(pto_vta).zfill(4)}-{num_local}] "
                            f"RECHAZADA: {res.get('mensaje')}"
                        )
                        proximo_afip += 1
                    else:
                        resumen["error_comunicacion"] += 1
                        resumen["detalles"].append(
                            f"Factura {factura_id} [{tipo} {str(pto_vta).zfill(4)}-{num_local}] "
                            f"ERROR COMUNICACIÓN: {res.get('mensaje')}"
                        )

            db.commit()
            return resumen

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Nota de crédito --------------------
    def generar_nota_credito(self, factura_id: int) -> Dict[str, Any]:
        """
        Genera una Nota de Crédito que anula la factura indicada.

        Importante:
        - En BD se siguen guardando importes negativos (lógica contable clásica).
        - Para AFIP, el wsfe_client ya se encarga de enviar los importes en positivo
          y de armar el CbteAsoc usando los campos cbte_asoc_*.
        - Las observaciones de ARCA SOLO se guardan si la NC NO queda aprobada.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)

            factura_original = repo.get_by_id(factura_id)
            if not factura_original:
                raise ValueError(f"Factura {factura_id} no encontrada.")

            items_original = repo.get_detalle_by_factura(factura_id)
            if not items_original:
                raise ValueError("La factura original no tiene ítems en el detalle.")

            tipo_orig = factura_original.get("tipo")
            pto_vta = factura_original.get("punto_venta")
            if not tipo_orig or not pto_vta:
                raise ValueError("La factura original no tiene tipo o punto de venta válido.")

            map_nc = {
                "FA": "NCA",
                "FB": "NCB",
                "FC": "NCC",
            }
            tipo_nc = map_nc.get(tipo_orig, "NCB")  # default B

            numero_nc = repo.get_next_numero(tipo_nc, int(pto_vta))

            items_nc: List[Dict[str, Any]] = []
            subtotal_nc = 0.0
            iva_nc = 0.0
            total_nc = 0.0

            for it in items_original:
                cantidad = float(it.get("cantidad") or 0.0)
                precio_unit = float(it.get("precio_unitario") or 0.0)
                alic_iva = float(it.get("alicuota_iva") or 0.0)

                neto_orig = float(it.get("importe_neto") or cantidad * precio_unit)
                iva_orig = float(it.get("importe_iva") or neto_orig * alic_iva / 100.0)
                total_orig = float(it.get("importe_total") or (neto_orig + iva_orig))

                # En la NC, en BD usamos importes negativos (anulan la original)
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
                f"NC que anula factura {tipo_orig} "
                f"{str(pto_vta).zfill(4)}-{factura_original.get('numero')}"
            )

            condicion_iva_nc_id = self._resolver_condicion_iva_receptor(
                db,
                factura_original,
            )

            # Campos cbte_asoc_* para que el wsfe_client pueda armar <CbtesAsoc>
            cabecera_nc = {
                "tipo": tipo_nc,
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
                # NUEVO: datos explícitos del comprobante asociado
                "cbte_asoc_tipo": tipo_orig,
                "cbte_asoc_pto_vta": int(pto_vta),
                "cbte_asoc_numero": factura_original.get("numero"),
            }

            nc_id = repo.insert_factura(cabecera_nc)
            repo.insert_detalle(nc_id, items_nc)

            # 1) Autenticación ARCA
            try:
                auth: ArcaAuthData = self._wsaa.get_auth()
            except Exception as e:
                import traceback
                print("ERROR al obtener auth en generar_nota_credito:", repr(e))
                traceback.print_exc()
                db.rollback()
                return {
                    "factura_original_id": factura_id,
                    "nc_id": nc_id,
                    "aprobada": False,
                    "rechazada": False,
                    "cae": None,
                    "fecha_cae": None,
                    "vto_cae": None,
                    "estado_nc_id": self.ESTADO_BORRADOR,
                    "estado_factura_original_nuevo": factura_original.get("estado_id"),
                    "errores": [],
                    "observaciones": [],
                    "mensaje": f"Error al obtener autenticación ARCA para NC: {e}",
                }

            factura_nc = repo.get_by_id(nc_id)
            factura_nc["condicion_iva_receptor_id"] = condicion_iva_nc_id
            factura_nc["cbte_asoc_tipo"] = tipo_orig
            factura_nc["cbte_asoc_pto_vta"] = int(pto_vta)
            factura_nc["cbte_asoc_numero"] = factura_original.get("numero")

            # 2) Llamar WSFE para solicitar CAE de la NC
            try:
                wsfe_result: ArcaWSFEResult = self._wsfe.solicitar_cae(
                    auth=auth,
                    factura=factura_nc,
                    items=items_nc,
                )
            except Exception as e:
                import traceback
                print("ERROR al llamar a WSFE.solicitar_cae en NC:", repr(e))
                traceback.print_exc()
                db.rollback()
                return {
                    "factura_original_id": factura_id,
                    "nc_id": nc_id,
                    "aprobada": False,
                    "rechazada": False,
                    "cae": None,
                    "fecha_cae": None,
                    "vto_cae": None,
                    "estado_nc_id": self.ESTADO_ERROR_COMUNICACION,
                    "estado_factura_original_nuevo": factura_original.get("estado_id"),
                    "errores": [],
                    "observaciones": [],
                    "mensaje": f"Error al invocar WSFE.solicitar_cae para NC: {e}",
                }

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

            # Observaciones de ARCA SOLO si la NC no fue aprobada
            if not wsfe_result.aprobada:
                partes: List[str] = []

                if wsfe_result.mensaje:
                    partes.append(wsfe_result.mensaje.strip())

                if wsfe_result.errores:
                    partes.append(
                        "Errores ARCA (NC):\n" + "\n".join(f"- {e}" for e in wsfe_result.errores)
                    )

                if wsfe_result.observaciones:
                    partes.append(
                        "Observaciones ARCA (NC):\n"
                        + "\n".join(f"- {o}" for o in wsfe_result.observaciones)
                    )

                texto_obs = "\n".join(p for p in partes if p).strip()
                if texto_obs:
                    self._actualizar_observaciones_factura(
                        db,
                        factura_id=nc_id,
                        mensaje=texto_obs,
                    )

            # ✅ ACÁ ESTÁ EL FIX: ya no dependemos de 19 (CAE Vencido).
            # Por defecto pasa a "Anulada" (16), o a "Anulada por NC" si existe
            # y fue resuelta por nombre al iniciar.
            estado_orig_nuevo = factura_original.get("estado_id")
            if wsfe_result.aprobada and self.ESTADO_ANULADA_POR_NC:
                repo.actualizar_estado(factura_id, self.ESTADO_ANULADA_POR_NC)
                estado_orig_nuevo = self.ESTADO_ANULADA_POR_NC

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
                "estado_nc_id": estado_nc,
                "estado_factura_original_nuevo": estado_orig_nuevo,
                "errores": wsfe_result.errores or [],
                "observaciones": wsfe_result.observaciones or [],
                "mensaje": wsfe_result.mensaje,
                "nc_tipo": nc_header.get("tipo") if nc_header else tipo_nc,
                "nc_pto_vta": nc_header.get("punto_venta") if nc_header else pto_vta,
                "nc_numero": nc_header.get("numero") if nc_header else numero_nc,
                "nc_total": nc_header.get("total") if nc_header else total_nc,
            }

        except Exception as ex:
            import traceback
            print("ERROR general en generar_nota_credito:", repr(ex))
            traceback.print_exc()
            db.rollback()
            return {
                "factura_original_id": factura_id,
                "nc_id": None,
                "aprobada": False,
                "rechazada": False,
                "cae": None,
                "fecha_cae": None,
                "vto_cae": None,
                "estado_nc_id": None,
                "estado_factura_original_nuevo": None,
                "errores": [],
                "observaciones": [],
                "mensaje": f"Error interno en generar_nota_credito: {ex}",
            }
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
                    SELECT tipo_doc
                    FROM clientes
                    WHERE id = :id
                    """
                ),
                {"id": cliente_id},
            ).mappings().first()
            if row:
                tipo_doc = (row.get("tipo_doc") or "").upper()
        except Exception:
            tipo_doc = None

        default_code = None
        if tipo_doc == "DNI":
            default_code = "CF"   # Consumidor Final
        elif tipo_doc == "CUIT":
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
