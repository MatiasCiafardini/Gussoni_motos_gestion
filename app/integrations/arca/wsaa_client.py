from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import base64
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
from app.integrations.arca.config import ArcaEnv
ARG = timezone(timedelta(hours=-3))

# -------------------- Carga de .env --------------------

# Estructura esperada:
#   APP_GUSSONI/
#       .env
#       app/
#         integrations/
#           arca/
#             wsaa_client.py  <-- este archivo
#
# Entonces: arca -> integrations -> app -> APP_GUSSONI  => parent.parent.parent.parent
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Cargar variables del .env si existe
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


# -------------------- Modelo de datos --------------------


@dataclass
class ArcaAuthData:
    """
    Datos de autenticación devueltos por el WSAA.

    - token / sign: se usan luego en el WS de Facturación (WSFEv1).
    - cuit: CUIT emisor (el tuyo).
    - expires_at: fecha/hora en que expira el Ticket de Acceso.
    """
    token: str
    sign: str
    cuit: str
    expires_at: datetime

    def is_expired(self, margin_seconds: int = 60) -> bool:
        """
        Indica si el TA está vencido (con un margen de seguridad).
        """
        now = datetime.now(self.expires_at.tzinfo)
        margin = timedelta(seconds=margin_seconds)
        return now + margin >= self.expires_at


# -------------------- Configuración --------------------


class ArcaConfig:
    """
    Configuración necesaria para hablar con WSAA.

    Se lee desde variables de entorno, pero podrías reemplazar esto
    para leer desde una tabla de configuración en tu BD si querés.
    """

    def __init__(
        self,
        cuit: str,
        cert_path: Path,
        key_path: Path,
        key_password: Optional[str],
        mode: str = "HOMOLOGACION",
        wsaa_url: Optional[str] = None,
    ) -> None:
        self.cuit = cuit
        self.cert_path = cert_path
        self.key_path = key_path
        self.key_password = key_password
        self.mode = (mode or "HOMOLOGACION").upper()

        # URLs oficiales de AFIP/ARCA para WSAA
        if wsaa_url:
            self.wsaa_url = wsaa_url
        else:
            if self.mode == "PRODUCCION":
                self.wsaa_url = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
            else:
                # Homologación / testing
                self.wsaa_url = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"

    @classmethod
    def from_env(cls) -> "ArcaConfig":
        """
        Crea la config leyendo desde variables de entorno.

        Variables esperadas:
          - ARCA_CUIT
          - ARCA_CERT_PATH
          - ARCA_KEY_PATH
          - ARCA_KEY_PASSWORD (opcional)
          - ARCA_MODO (HOMOLOGACION | PRODUCCION, opcional)
          - ARCA_WSAA_URL (opcional, para override manual)
        """
        cuit = os.getenv("ARCA_CUIT", "").strip()
        cert = os.getenv("ARCA_CERT_PATH", "").strip()
        key = os.getenv("ARCA_KEY_PATH", "").strip()
        key_pass = os.getenv("ARCA_KEY_PASSWORD", "").strip() or None
        modo = os.getenv("ARCA_MODO", "HOMOLOGACION").strip() or "HOMOLOGACION"
        wsaa_url = os.getenv("ARCA_WSAA_URL", "").strip() or None

        if not cuit:
            raise RuntimeError("Config ARCA: falta ARCA_CUIT en las variables de entorno.")
        if not cert:
            raise RuntimeError("Config ARCA: falta ARCA_CERT_PATH en las variables de entorno.")
        if not key:
            raise RuntimeError("Config ARCA: falta ARCA_KEY_PATH en las variables de entorno.")

        return cls(
            cuit=ArcaEnv.CUIT,
            cert_path=ArcaEnv.CERT,
            key_path=ArcaEnv.KEY,
            key_password=None,
            mode="PRODUCCION" if ArcaEnv.IS_PROD else "HOMOLOGACION",
            wsaa_url=ArcaEnv.WSAA_URL,
        )


# -------------------- Cliente WSAA --------------------


class ArcaWSAAClient:
    """
    Cliente del WebService de Autenticación y Autorización (WSAA).

    Uso típico:
        wsaa = ArcaWSAAClient()
        auth = wsaa.get_auth()
        # auth.token, auth.sign, auth.cuit, auth.expires_at
    """

    SERVICE_NAME = "wsfe"  # identificador del WSN (facturación electrónica)
    TA_PATH = BASE_DIR / "arca_ta.xml"  # cache en disco del TA

    def __init__(self, config: Optional[ArcaConfig] = None) -> None:
        self._config = config or ArcaConfig.from_env()
        self._cached_auth: Optional[ArcaAuthData] = None

    # -------- API pública --------

    def get_auth(self, force_renew: bool = False) -> ArcaAuthData:
        """
        Devuelve un TA válido (token+sign) para el servicio configurado.

        Orden:
        1) Si hay TA cacheado en memoria y sigue vigente → lo devuelve.
        2) Si hay TA en disco (arca_ta.xml) y sigue vigente → lo carga y lo devuelve.
        3) Si no hay TA válido → pide uno nuevo al WSAA.
           - Si WSAA responde coe.alreadyAuthenticated → reintenta usando el TA en disco.
        """

        # 1) Cache en memoria
        if not force_renew and self._cached_auth is not None:
            if not self._cached_auth.is_expired():
                return self._cached_auth

        # 2) Intentar cache en disco
        if not force_renew:
            ta_disk = self._load_ta_from_disk()
            if ta_disk is not None and not ta_disk.is_expired():
                self._cached_auth = ta_disk
                return ta_disk

        # 3) Pedir TA nuevo al WSAA
        try:
            auth = self._request_new_ticket()
            self._cached_auth = auth
            self._save_ta_to_disk(auth)
            return auth
        except RuntimeError as e:
            msg = str(e)
            # Manejo especial: ya hay un TA válido en WSAA
            if "coe.alreadyAuthenticated" in msg:
                # Intentamos reutilizar el TA del disco
                ta_disk = self._load_ta_from_disk()
                if ta_disk is not None and not ta_disk.is_expired():
                    self._cached_auth = ta_disk
                    return ta_disk

                # Si WSAA dice que ya hay TA pero nosotros no tenemos nada local → error claro
                raise RuntimeError(
                    "WSAA devolvió 'alreadyAuthenticated' pero no se encontró un TA local válido. "
                    "Probá borrar el TA en AFIP/ARCA o esperar a que venza el actual."
                ) from e

            # Cualquier otro error se propaga
            raise

    # -------- Cache en disco del TA --------

    def _load_ta_from_disk(self) -> Optional[ArcaAuthData]:
        """
        Lee arca_ta.xml desde BASE_DIR si existe.
        Formato simple:
        <TA>
          <token>...</token>
          <sign>...</sign>
          <expires_at>ISO 8601</expires_at>
        </TA>
        """
        if not self.TA_PATH.exists():
            return None

        try:
            xml = self.TA_PATH.read_text(encoding="utf-8")
            root = ET.fromstring(xml)

            token = root.findtext("token") or ""
            sign = root.findtext("sign") or ""
            expires_txt = root.findtext("expires_at") or ""

            if not token or not sign or not expires_txt:
                return None

            expires_at = datetime.fromisoformat(expires_txt)

            return ArcaAuthData(
                token=token,
                sign=sign,
                cuit=self._config.cuit,
                expires_at=expires_at,
            )
        except Exception as ex:
            print(f"[WSAA] Error leyendo TA de disco ({self.TA_PATH}): {ex}")
            return None

    def _save_ta_to_disk(self, auth: ArcaAuthData) -> None:
        """
        Guarda un TA muy simple en arca_ta.xml para reuso.
        """
        try:
            xml = f"""<TA>
  <token>{auth.token}</token>
  <sign>{auth.sign}</sign>
  <expires_at>{auth.expires_at.isoformat()}</expires_at>
</TA>
"""
            self.TA_PATH.write_text(xml, encoding="utf-8")
        except Exception as ex:
            print(f"[WSAA] No se pudo guardar TA en disco ({self.TA_PATH}): {ex}")

    # -------- Flujo interno: pedir TA --------

    def _request_new_ticket(self) -> ArcaAuthData:
        """
        1) Genera el LoginTicketRequest (XML)
        2) Lo firma con OpenSSL (CMS / PKCS#7)
        3) Lo manda al WSAA via SOAP
        4) Parsea LoginTicketResponse y arma ArcaAuthData
        """
        ltr_xml = self._build_login_ticket_request()
        cms_b64 = self._sign_ltr_with_openssl(ltr_xml)
        response_xml = self._call_wsaa_login_cms(cms_b64)
        auth = self._parse_login_ticket_response(response_xml)
        return auth

    # -------- 1) LoginTicketRequest.xml --------

    def _build_login_ticket_request(self) -> str:
        now = datetime.now(ARG)

        # AFIP recomienda un margen
        generation_time = now - timedelta(minutes=5)
        expiration_time = now + timedelta(hours=12)
        unique_id = int(now.timestamp())

        def _fmt(dt: datetime) -> str:
            # Convierte 2025-02-25T15:20:00-0300 → 2025-02-25T15:20:00-03:00
            txt = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
            return txt[:-2] + ":" + txt[-2:]

        root = ET.Element("loginTicketRequest", version="1.0")
        header = ET.SubElement(root, "header")

        uid = ET.SubElement(header, "uniqueId")
        uid.text = str(unique_id)

        gen = ET.SubElement(header, "generationTime")
        gen.text = _fmt(generation_time)

        exp = ET.SubElement(header, "expirationTime")
        exp.text = _fmt(expiration_time)

        service = ET.SubElement(root, "service")
        service.text = self.SERVICE_NAME

        xml_bytes = ET.tostring(root, encoding="utf-8", method="xml")
        return xml_bytes.decode("utf-8")

    # -------- 2) Firma PKCS#7 con OpenSSL --------

    def _sign_ltr_with_openssl(self, ltr_xml: str) -> str:
        """
        Usa OpenSSL por línea de comandos para:

        - Firmar el XML en formato CMS (DER)
        - Devolverlo codificado en base64 (string)

        Requiere que 'openssl' esté en el PATH del sistema.
        """
        if not self._config.cert_path.exists():
            raise FileNotFoundError(f"Certificado ARCA no encontrado: {self._config.cert_path}")
        if not self._config.key_path.exists():
            raise FileNotFoundError(f"Clave privada ARCA no encontrada: {self._config.key_path}")

        # Guardamos el XML temporalmente
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".xml") as f_xml:
            f_xml.write(ltr_xml)
            xml_path = f_xml.name

        try:
            cmd = [
                "openssl",
                "smime",
                "-sign",
                "-signer", str(self._config.cert_path),
                "-inkey", str(self._config.key_path),
                "-outform", "DER",
                "-nodetach",
                "-noattr",
                "-in", xml_path,
            ]

            if self._config.key_password:
                cmd.extend(["-passin", f"pass:{self._config.key_password}"])

            # Ejecutamos openssl y capturamos la salida (CMS en DER)
            proc = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            cms_der = proc.stdout
            if not cms_der:
                raise RuntimeError(f"OpenSSL no devolvió datos CMS. STDERR: {proc.stderr.decode(errors='ignore')}")

            # Codificamos DER → base64 (string)
            cms_b64 = base64.b64encode(cms_der).decode("ascii")
            return cms_b64

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Error ejecutando OpenSSL (smime sign). "
                f"Return code: {e.returncode}, STDERR: {e.stderr.decode(errors='ignore')}"
            ) from e
        finally:
            # Borramos el archivo temporal
            try:
                os.unlink(xml_path)
            except OSError:
                pass

    # -------- 3) Llamar al WSAA (SOAP loginCms) --------

    def _call_wsaa_login_cms(self, cms_b64: str) -> str:
        """
        Llama al WSAA con el CMS en base64 usando SOAP.
        """
        soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov">
   <soapenv:Header/>
   <soapenv:Body>
      <wsaa:loginCms>
         <wsaa:in0>{cms_b64}</wsaa:in0>
      </wsaa:loginCms>
   </soapenv:Body>
</soapenv:Envelope>
"""

        data = soap_envelope.encode("utf-8")
        req = urllib.request.Request(
            self._config.wsaa_url,
            data=data,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "",  # Afip no requiere un SOAPAction específico
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            # MUY IMPORTANTE: acá el body puede traer coe.alreadyAuthenticated
            raise RuntimeError(
                f"Error HTTP al llamar WSAA ({e.code}): {body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"No se pudo conectar al WSAA: {e}") from e

        return resp_data.decode("utf-8", errors="ignore")

    # -------- 4) Parsear LoginTicketResponse --------

    def _parse_login_ticket_response(self, soap_xml: str) -> ArcaAuthData:
        """
        Extrae el LoginTicketResponse del SOAP y devuelve ArcaAuthData.
        """
        # 1) Parsear SOAP
        root = ET.fromstring(soap_xml)

        # Namespaces usados en WSAA
        ns = {
            "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "wsaa": "http://wsaa.view.sua.dvadac.desein.afip.gov",
        }

        # Buscamos el contenido de loginCmsReturn dentro del envelope
        login_return = None

        # Intento 1: usando prefijos/namespace
        node = root.find(".//wsaa:loginCmsReturn", ns)
        if node is not None and node.text:
            login_return = node.text.strip()

        # Intento 2: por si no se respeta el namespace en la respuesta
        if not login_return:
            for elem in root.iter():
                if elem.tag.endswith("loginCmsReturn") and elem.text:
                    login_return = elem.text.strip()
                    break

        if not login_return:
            raise RuntimeError("No se encontró loginCmsReturn en la respuesta del WSAA.")

        # 2) Parsear el LoginTicketResponse (XML incluido dentro de loginCmsReturn)
        ltr_root = ET.fromstring(login_return)

        # En general, el XML no tiene namespaces, así que buscamos directo
        token = self._find_text_anywhere(ltr_root, "token")
        sign = self._find_text_anywhere(ltr_root, "sign")
        expiration = self._find_text_anywhere(ltr_root, "expirationTime")

        if not token or not sign or not expiration:
            raise RuntimeError("No se pudieron extraer token/sign/expirationTime del LoginTicketResponse.")

        # Parsear fecha de expiración (ISO 8601)
        expires_at = self._parse_datetime_iso(expiration)

        return ArcaAuthData(
            token=token,
            sign=sign,
            cuit=self._config.cuit,
            expires_at=expires_at,
        )

    @staticmethod
    def _find_text_anywhere(root: ET.Element, tag_name: str) -> Optional[str]:
        """
        Busca el texto de la primera coincidencia de un tag (sin importar namespace).
        """
        for elem in root.iter():
            if elem.tag.endswith(tag_name) and elem.text:
                return elem.text.strip()
        return None

    @staticmethod
    def _parse_datetime_iso(value: str) -> datetime:
        """
        Intenta parsear una fecha/hora ISO 8601. Ej:
        2025-11-24T23:59:59-03:00
        2025-11-24T23:59:59
        """
        value = value.strip()
        # fromisoformat soporta offsets tipo -03:00 a partir de Python 3.7
        try:
            return datetime.fromisoformat(value)
        except Exception:
            # fallback sin zona horaria
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            except Exception as ex:
                raise ValueError(f"No se pudo parsear la fecha de expiración: {value}") from ex
