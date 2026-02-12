from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from app.core.config import settings

from app.services.catalogos_service import CatalogosService

import ssl
# -------------------- Resultado WSFE --------------------


@dataclass
class ArcaWSFEResult:
    """
    Resultado de una llamada a WSFE (FECAESolicitar).

    - aprobada: True si el comprobante fue aceptado
    - rechazada: True si fue rechazado explícitamente
    - cae: CAE devuelto por ARCA/AFIP (si aprobada)
    - fecha_cae: fecha de proceso / emisión del CAE (texto, para guardar tal cual)
    - vto_cae: fecha de vencimiento del CAE (texto, para guardar en BD)
    - errores: lista de códigos/mensajes de error
    - observaciones: observaciones/leyendas
    - mensaje: resumen legible del resultado (para mostrar en UI / observaciones)
    """
    aprobada: bool
    rechazada: bool
    cae: Optional[str]
    fecha_cae: Optional[str]
    vto_cae: Optional[str]
    errores: List[str]
    observaciones: List[str]
    mensaje: str


# -------------------- Configuración WSFE --------------------


class ArcaWSFEConfig:
    def __init__(self) -> None:
        self.mode = (settings.ARCA_ENV or "HOMOLOGACION").upper()

        if self.mode == "PRODUCCION":
            self.wsfe_url = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"
        else:
            self.wsfe_url = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"



# -------------------- Cliente WSFE --------------------


class ArcaWSFEClient:
    """
    Cliente del WebService de Facturación Electrónica (WSFEv1).

    Está pensado para integrarse con FacturasService.autorizar_en_arca,
    que le pasa:

      - auth: ArcaAuthData (token, sign, cuit)
      - factura: dict con cabecera (get_by_id del repo)
      - items: detalle de la factura (facturas_detalle)
    """

    def __init__(self, config: Optional[ArcaWSFEConfig] = None) -> None:
        self._config = config or ArcaWSFEConfig()


    # -------- API principal --------

    def solicitar_cae(
        self,
        auth: Any,
        factura: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> ArcaWSFEResult:
        """
        Orquesta la llamada a FECAESolicitar.

        - Arma el SOAP XML a partir de auth + factura + items
        - Envía el request al endpoint WSFE
        - Parsea el response
        - Devuelve un ArcaWSFEResult listo para usar
        """
        if not items:
            raise ValueError("No se puede autorizar una factura sin ítems.")

        soap_xml = self._build_fe_cae_solicitar_request(auth, factura, items)
        response_xml = self._call_wsfe(soap_xml)
        return self._parse_fe_cae_solicitar_response(response_xml)
    def fe_comp_consultar(
        self,
        auth,
        cbte_tipo: int,
        pto_vta: int,
        cbte_nro: int,
    ) -> Dict[str, Any]:
        """
        Consulta un comprobante ya autorizado en AFIP (FECompConsultar).
        Devuelve un dict normalizado.
        """

        soap = f"""<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:ar="http://ar.gov.afip.dif.FEV1/">
    <soapenv:Header/>
    <soapenv:Body>
        <ar:FECompConsultar>
            <ar:Auth>
                <ar:Token>{self._escape(auth.token)}</ar:Token>
                <ar:Sign>{self._escape(auth.sign)}</ar:Sign>
                <ar:Cuit>{self._escape(str(auth.cuit))}</ar:Cuit>
            </ar:Auth>
            <ar:FeCompConsReq>
                <ar:CbteTipo>{int(cbte_tipo)}</ar:CbteTipo>
                <ar:PtoVta>{int(pto_vta)}</ar:PtoVta>
                <ar:CbteNro>{int(cbte_nro)}</ar:CbteNro>
            </ar:FeCompConsReq>
        </ar:FECompConsultar>
    </soapenv:Body>
    </soapenv:Envelope>
    """

        response_xml = self._call_wsfe_action(soap, "FECompConsultar")

        try:
            root = ET.fromstring(response_xml)
        except ET.ParseError as ex:
            raise RuntimeError(
                f"Respuesta FECompConsultar no es XML válido: {ex}. "
                f"Respuesta cruda: {response_xml[:500]}"
            ) from ex

        ns = {
            "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "ar": "http://ar.gov.afip.dif.FEV1/",
        }

        result = root.find(".//ar:FECompConsultarResult", ns)
        if result is None:
            for elem in root.iter():
                if elem.tag.endswith("FECompConsultarResult"):
                    result = elem
                    break

        if result is None:
            raise RuntimeError("No se encontró FECompConsultarResult en la respuesta de WSFE.")

        return {
            "resultado": self._find_text_anywhere(result, "Resultado"),
            "cae": self._find_text_anywhere(result, "CodAutorizacion"),
            "fecha_cae": self._find_text_anywhere(result, "FchProceso"),
            "vto_cae": self._find_text_anywhere(result, "FchVto"),
            "imp_total": self._find_text_anywhere(result, "ImpTotal"),
            "errores": self._collect_errors(result),
            "observaciones": self._collect_observaciones(result),
            "raw_xml": response_xml,
        }


    def fe_comp_ultimo_autorizado(
        self,
        auth: Any,
        cbte_tipo: int,
        pto_vta: int,
    ) -> Dict[str, Any]:
        """
        Wrapper de FECompUltimoAutorizado.

        Devuelve un dict:
          {
            "cbte_tipo": int,
            "pto_vta": int,
            "cbte_nro": int,
            "errores": [str, ...]
          }

        Si algo raro pasa, levanta RuntimeError para que la capa de servicio
        decida si cae a BD.
        """
        soap = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ar="http://ar.gov.afip.dif.FEV1/">
   <soapenv:Header/>
   <soapenv:Body>
      <ar:FECompUltimoAutorizado>
         <ar:Auth>
            <ar:Token>{self._escape(auth.token)}</ar:Token>
            <ar:Sign>{self._escape(auth.sign)}</ar:Sign>
            <ar:Cuit>{self._escape(str(auth.cuit))}</ar:Cuit>
         </ar:Auth>
         <ar:PtoVta>{int(pto_vta)}</ar:PtoVta>
         <ar:CbteTipo>{int(cbte_tipo)}</ar:CbteTipo>
      </ar:FECompUltimoAutorizado>
   </soapenv:Body>
</soapenv:Envelope>
"""
        response_xml = self._call_wsfe_action(soap, "FECompUltimoAutorizado")

        try:
            root = ET.fromstring(response_xml)
        except ET.ParseError as ex:
            raise RuntimeError(
                f"Respuesta FECompUltimoAutorizado no es XML válido: {ex}. "
                f"Respuesta cruda: {response_xml[:500]}"
            ) from ex

        ns = {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/", "ar": "http://ar.gov.afip.dif.FEV1/"}

        fe_result = root.find(".//ar:FECompUltimoAutorizadoResult", ns)
        if fe_result is None:
            for elem in root.iter():
                if elem.tag.endswith("FECompUltimoAutorizadoResult"):
                    fe_result = elem
                    break

        if fe_result is None:
            raise RuntimeError("No se encontró FECompUltimoAutorizadoResult en la respuesta del WSFE.")

        pto_resp = self._find_text_anywhere(fe_result, "PtoVta")
        tipo_resp = self._find_text_anywhere(fe_result, "CbteTipo")
        nro_resp = self._find_text_anywhere(fe_result, "CbteNro")

        errores = self._collect_errors(fe_result)

        try:
            pto_int = int(pto_resp) if pto_resp is not None else int(pto_vta)
        except Exception:
            pto_int = int(pto_vta)

        try:
            tipo_int = int(tipo_resp) if tipo_resp is not None else int(cbte_tipo)
        except Exception:
            tipo_int = int(cbte_tipo)

        try:
            nro_int = int(nro_resp) if nro_resp is not None else 0
        except Exception:
            nro_int = 0

        return {"cbte_tipo": tipo_int, "pto_vta": pto_int, "cbte_nro": nro_int, "errores": errores}

    # -------- Construcción FECAESolicitar --------

    def _build_fe_cae_solicitar_request(
        self,
        auth: Any,
        factura: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> str:
        """
        Construye el Envelope SOAP de FECAESolicitar.
        """

        tipo_id = factura.get("tipo_comprobante_id")
        if not tipo_id:
            raise ValueError("Factura sin tipo_comprobante_id.")


        catalogos = CatalogosService()
        tipo_data = catalogos.get_tipo_comprobante_by_id(int(tipo_id))

        if not tipo_data:
            raise ValueError(f"No se encontró tipo_comprobante_id {tipo_id} en catálogo.")

        tipo_cbte_str = tipo_data["codigo"]

        pto_vta = int(factura.get("punto_venta") or 0)
        numero = int(factura.get("numero") or 0)

        if not tipo_cbte_str or pto_vta <= 0 or numero <= 0:
            raise ValueError("Faltan datos de numeración en factura (tipo, punto_venta, numero).")

        cbte_tipo = self._map_tipo_comprobante_to_afip_code(tipo_cbte_str)

        # NC / ND
        es_nc_nd = cbte_tipo in (2, 3, 7, 8, 12, 13)

        cbte_fch = self._to_afip_date(factura.get("fecha_emision"))

        imp_neto = float(factura.get("subtotal") or 0.0)
        imp_iva = float(factura.get("iva") or 0.0)
        imp_total = float(factura.get("total") or 0.0)

        # Para NC / ND AFIP no permite negativos
        if es_nc_nd:
            imp_neto = abs(imp_neto)
            imp_iva = abs(imp_iva)
            imp_total = abs(imp_total)

        moneda = (factura.get("moneda") or "ARS").upper()
        mon_id, mon_cotiz = self._map_moneda(moneda, float(factura.get("cotizacion") or 1.0))

        concepto = 1  # productos

        doc_tipo, doc_nro = self._extract_doc_from_factura(factura)

        condicion_iva_receptor_id = self._extract_condicion_iva_receptor_id(factura)
        condicion_iva_xml = ""
        if condicion_iva_receptor_id is not None:
            condicion_iva_xml = (
                f"\n                  <ar:CondicionIVAReceptorId>{int(condicion_iva_receptor_id)}</ar:CondicionIVAReceptorId>"
            )

        alic_iva_id, base_imp, importe_iva = self._build_iva_block(items, imp_neto, imp_iva)

        cbtes_asoc_xml = self._build_cbtes_asoc_xml(factura, cbte_tipo)

        cbte_desde = numero
        cbte_hasta = numero

        soap = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ar="http://ar.gov.afip.dif.FEV1/">
   <soapenv:Header/>
   <soapenv:Body>
      <ar:FECAESolicitar>
         <ar:Auth>
            <ar:Token>{self._escape(auth.token)}</ar:Token>
            <ar:Sign>{self._escape(auth.sign)}</ar:Sign>
            <ar:Cuit>{self._escape(str(auth.cuit))}</ar:Cuit>
         </ar:Auth>
         <ar:FeCAEReq>
            <ar:FeCabReq>
               <ar:CantReg>1</ar:CantReg>
               <ar:PtoVta>{pto_vta}</ar:PtoVta>
               <ar:CbteTipo>{cbte_tipo}</ar:CbteTipo>
            </ar:FeCabReq>
            <ar:FeDetReq>
               <ar:FECAEDetRequest>
                  <ar:Concepto>{concepto}</ar:Concepto>
                  <ar:DocTipo>{doc_tipo}</ar:DocTipo>
                  <ar:DocNro>{doc_nro}</ar:DocNro>
                  <ar:CbteDesde>{cbte_desde}</ar:CbteDesde>
                  <ar:CbteHasta>{cbte_hasta}</ar:CbteHasta>
                  <ar:CbteFch>{cbte_fch}</ar:CbteFch>
                  <ar:ImpTotal>{imp_total:.2f}</ar:ImpTotal>
                  <ar:ImpTotConc>0.00</ar:ImpTotConc>
                  <ar:ImpNeto>{imp_neto:.2f}</ar:ImpNeto>
                  <ar:ImpOpEx>0.00</ar:ImpOpEx>
                  <ar:ImpTrib>0.00</ar:ImpTrib>
                  <ar:ImpIVA>{imp_iva:.2f}</ar:ImpIVA>
                  <ar:MonId>{mon_id}</ar:MonId>
                  <ar:MonCotiz>{mon_cotiz:.6f}</ar:MonCotiz>{condicion_iva_xml}{cbtes_asoc_xml}
                  <ar:Iva>
                     <ar:AlicIva>
                        <ar:Id>{alic_iva_id}</ar:Id>
                        <ar:BaseImp>{base_imp:.2f}</ar:BaseImp>
                        <ar:Importe>{importe_iva:.2f}</ar:Importe>
                     </ar:AlicIva>
                  </ar:Iva>
               </ar:FECAEDetRequest>
            </ar:FeDetReq>
         </ar:FeCAEReq>
      </ar:FECAESolicitar>
   </soapenv:Body>
</soapenv:Envelope>
"""
        return soap

    # -------- Llamada HTTP --------

    def _call_wsfe(self, soap_xml: str) -> str:
        return self._call_wsfe_action(soap_xml, "FECAESolicitar")

    def _call_wsfe_action(self, soap_xml: str, action: str) -> str:
        data = soap_xml.encode("utf-8")

        soap_action = f"http://ar.gov.afip.dif.FEV1/{action}"
    
        req = urllib.request.Request(
            self._config.wsfe_url,
            data=data,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": soap_action,  # ✅ BIEN
            },
            method="POST",
        )

        try:
            context = ssl.create_default_context()
            context.set_ciphers("DEFAULT@SECLEVEL=1")

            with urllib.request.urlopen(req, timeout=30, context=context) as resp:
                return resp.read().decode("utf-8", errors="ignore")

        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            raise RuntimeError(
                f"Error WSFE HTTP {e.code} ({action}): {body}"
            ) from e

        except urllib.error.URLError as e:
            raise RuntimeError(
                f"No se pudo conectar a WSFE ({action}): {e}"
            ) from e


    # -------- Parseo respuesta FECAESolicitar --------

    def _parse_fe_cae_solicitar_response(self, soap_xml: str) -> ArcaWSFEResult:
        """
        Parsea el SOAP de respuesta de FECAESolicitar y devuelve un ArcaWSFEResult.
        Maneja también el caso en que AFIP devuelva HTML en vez de XML.
        """
        try:
            root = ET.fromstring(soap_xml)
        except ET.ParseError as ex:
            msg = f"Respuesta WSFE no es XML válido: {ex}. Respuesta cruda: {soap_xml[:500]}"
            return ArcaWSFEResult(
                aprobada=False,
                rechazada=False,
                cae=None,
                fecha_cae=None,
                vto_cae=None,
                errores=[],
                observaciones=[],
                mensaje=msg,
            )

        ns = {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/", "ar": "http://ar.gov.afip.dif.FEV1/"}

        fe_result = root.find(".//ar:FECAESolicitarResult", ns)
        if fe_result is None:
            for elem in root.iter():
                if elem.tag.endswith("FECAESolicitarResult"):
                    fe_result = elem
                    break

        if fe_result is None:
            msg = "No se encontró FECAESolicitarResult en la respuesta del WSFE."
            return ArcaWSFEResult(
                aprobada=False,
                rechazada=False,
                cae=None,
                fecha_cae=None,
                vto_cae=None,
                errores=[msg],
                observaciones=[],
                mensaje=msg,
            )

        errores: List[str] = []
        observaciones: List[str] = []

        errores.extend(self._collect_errors(fe_result))

        det_resp = None
        for elem in fe_result.iter():
            if elem.tag.endswith("FECAEDetResponse"):
                det_resp = elem
                break

        cae = None
        vto_cae = None
        fecha_cae = None
        resultado = None

        if det_resp is not None:
            resultado = self._find_text_anywhere(det_resp, "Resultado")
            cae = self._find_text_anywhere(det_resp, "CAE")
            vto_cae = self._find_text_anywhere(det_resp, "CAEFchVto")
            # AFIP suele devolver FchProceso (YYYYMMDD) cuando procesa el CAE
            fecha_cae = self._find_text_anywhere(det_resp, "FchProceso")
            observaciones.extend(self._collect_observaciones(det_resp))
        else:
            if not errores:
                errores.append("No se encontró FECAEDetResponse en la respuesta de WSFE.")

        mensaje = self._build_result_message(resultado, cae, vto_cae, fecha_cae, errores, observaciones)

        aprobada = (resultado or "").upper() == "A"
        rechazada = (resultado or "").upper() == "R"

        return ArcaWSFEResult(
            aprobada=aprobada,
            rechazada=rechazada,
            cae=cae,
            fecha_cae=fecha_cae,
            vto_cae=vto_cae,
            errores=errores,
            observaciones=observaciones,
            mensaje=mensaje,
        )

    # -------- Utilidades de parseo --------

    @staticmethod
    def _find_text_anywhere(root: ET.Element, tag_name: str) -> Optional[str]:
        for elem in root.iter():
            if elem.tag.endswith(tag_name) and elem.text:
                return elem.text.strip()
        return None

    @staticmethod
    def _collect_errors(root: ET.Element) -> List[str]:
        errores: List[str] = []
        for elem in root.iter():
            if elem.tag.endswith("Err"):
                code = ""
                msg = ""
                for ch in elem:
                    if ch.tag.endswith("Code") and ch.text:
                        code = ch.text.strip()
                    if ch.tag.endswith("Msg") and ch.text:
                        msg = ch.text.strip()
                if code or msg:
                    errores.append(f"{code} - {msg}".strip(" -"))
        return errores

    @staticmethod
    def _collect_observaciones(root: ET.Element) -> List[str]:
        obs: List[str] = []
        for elem in root.iter():
            if elem.tag.endswith("Obs"):
                code = ""
                msg = ""
                for ch in elem:
                    if ch.tag.endswith("Code") and ch.text:
                        code = ch.text.strip()
                    if ch.tag.endswith("Msg") and ch.text:
                        msg = ch.text.strip()
                if code or msg:
                    obs.append(f"{code} - {msg}".strip(" -"))
        return obs

    @staticmethod
    def _build_result_message(
        resultado: Optional[str],
        cae: Optional[str],
        vto_cae: Optional[str],
        fecha_cae: Optional[str],
        errores: List[str],
        observaciones: List[str],
    ) -> str:
        parts: List[str] = []

        if resultado:
            parts.append(f"Resultado: {resultado}")
        if cae:
            parts.append(f"CAE: {cae}")
        if fecha_cae:
            parts.append(f"FchProceso: {fecha_cae}")
        if vto_cae:
            parts.append(f"Vto CAE: {vto_cae}")

        if errores:
            parts.append("Errores: " + " | ".join(errores))
        if observaciones:
            parts.append("Obs: " + " | ".join(observaciones))

        return " - ".join(parts) if parts else "Sin información devuelta por WSFE."

    # -------- Mapeos / Helpers de negocio --------

    @staticmethod
    def _map_tipo_comprobante_to_afip_code(codigo: str) -> int:
        codigo = codigo.upper()
        mapping = {
            "FA": 1,
            "FB": 6,
            "FC": 11,
            "NCA": 3,
            "NCB": 8,
            "NCC": 13,
            "NDA": 2,
            "NDB": 7,
            "NDC": 12,
        }
        if codigo not in mapping:
            raise ValueError(f"Tipo de comprobante no mapeado a código AFIP: {codigo}")
        return mapping[codigo]

    @staticmethod
    def _to_afip_date(value: Any) -> str:
        if value is None:
            return datetime.today().strftime("%Y%m%d")

        if isinstance(value, datetime):
            return value.strftime("%Y%m%d")

        s = str(value).strip()
        if not s:
            return datetime.today().strftime("%Y%m%d")

        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s.replace("-", "")[:8]

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                dt = datetime.strptime(s[:10], fmt)
                return dt.strftime("%Y%m%d")
            except Exception:
                continue

        return s.replace("-", "")[:8]

    @staticmethod
    def _map_moneda(moneda: str, cotizacion: float) -> Tuple[str, float]:
        moneda = moneda.upper()
        if moneda in ("ARS", "PES"):
            return "PES", 1.0
        return moneda, float(cotizacion or 1.0)

    @staticmethod
    def _extract_doc_from_factura(factura: Dict[str, Any]) -> Tuple[int, int]:
        """
        Extrae DocTipo y DocNro usando directamente el código ARCA
        guardado en cliente_tipo_doc_id.
        """

        doc_tipo = factura.get("cliente_tipo_doc_id")
        nro_doc_raw = factura.get("cliente_nro_doc")

        if not doc_tipo:
            # fallback ultra defensivo → consumidor final
            return 99, 0

        nro_digits = "".join(ch for ch in str(nro_doc_raw) if ch.isdigit()) or "0"

        try:
            return int(doc_tipo), int(nro_digits)
        except Exception:
            return 99, 0


    @staticmethod
    def _extract_condicion_iva_receptor_id(factura: Dict[str, Any]) -> Optional[int]:
        for key in ("condicion_iva_receptor_id", "cliente_condicion_iva_receptor_id", "condicion_iva_receptor"):
            val = factura.get(key)
            if val in (None, "", 0, "0"):
                continue
            try:
                return int(val)
            except Exception:
                continue
        return None

    @staticmethod
    def _build_iva_block(
        items: List[Dict[str, Any]],
        imp_neto: float,
        imp_iva: float,
    ) -> Tuple[int, float, float]:
        # AFIP: Id 5 = 21%
        alic_id = 5
        base_imp = abs(float(imp_neto or 0.0))
        importe_iva = abs(float(imp_iva or 0.0))
        return alic_id, base_imp, importe_iva

    def _build_cbtes_asoc_xml(self, factura: Dict[str, Any], cbte_tipo_actual: int) -> str:
        """
        Construye el bloque <CbtesAsoc> para Notas de Crédito / Débito.

        Prioridad:
        1) Campos explícitos en factura:
           - cbte_asoc_tipo  (ej: 'FB')
           - cbte_asoc_pto_vta
           - cbte_asoc_numero
        2) Parseo de observaciones con formato:
           'NC que anula factura FB 0002-2'
        """
        if cbte_tipo_actual not in (2, 3, 7, 8, 12, 13):
            return ""

        tipo_orig = factura.get("cbte_asoc_tipo")
        pto_vta_orig = factura.get("cbte_asoc_pto_vta")
        nro_orig = factura.get("cbte_asoc_numero")

        # 1) Campos explícitos
        try:
            if tipo_orig and pto_vta_orig and nro_orig:
                tipo_afip = self._map_tipo_comprobante_to_afip_code(str(tipo_orig))
                pto_vta_int = int(pto_vta_orig)
                nro_int = int(nro_orig)
                return (
                    "\n                  <ar:CbtesAsoc>\n"
                    "                     <ar:CbteAsoc>\n"
                    f"                        <ar:Tipo>{tipo_afip}</ar:Tipo>\n"
                    f"                        <ar:PtoVta>{pto_vta_int}</ar:PtoVta>\n"
                    f"                        <ar:Nro>{nro_int}</ar:Nro>\n"
                    "                     </ar:CbteAsoc>\n"
                    "                  </ar:CbtesAsoc>"
                )
        except Exception:
            pass

        # 2) Observaciones
        obs = str(factura.get("observaciones") or "")
        marker = "factura "
        idx = obs.lower().find(marker)
        if idx != -1:
            try:
                resto = obs[idx + len(marker):].strip()  # "FB 0002-2"
                partes = resto.split()
                if len(partes) >= 2:
                    tipo_str = partes[0]
                    nro_str = partes[1]
                    if "-" in nro_str:
                        pv_str, num_str = nro_str.split("-", 1)
                        tipo_afip = self._map_tipo_comprobante_to_afip_code(tipo_str)
                        pto_vta_int = int(pv_str)
                        nro_int = int(num_str)
                        return (
                            "\n                  <ar:CbtesAsoc>\n"
                            "                     <ar:CbteAsoc>\n"
                            f"                        <ar:Tipo>{tipo_afip}</ar:Tipo>\n"
                            f"                        <ar:PtoVta>{pto_vta_int}</ar:PtoVta>\n"
                            f"                        <ar:Nro>{nro_int}</ar:Nro>\n"
                            "                     </ar:CbteAsoc>\n"
                            "                  </ar:CbtesAsoc>"
                        )
            except Exception:
                return ""

        return ""

    @staticmethod
    def _escape(value: str) -> str:
        if value is None:
            return ""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
