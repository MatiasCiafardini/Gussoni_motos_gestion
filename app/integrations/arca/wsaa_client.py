from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import base64
import subprocess
import tempfile
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from app.shared.openssl import get_openssl_path

from app.core.config import settings

ARG = timezone(timedelta(hours=-3))


# ======================================================================
# MODELO DE DATOS
# ======================================================================

@dataclass
class ArcaAuthData:
    """
    Datos de autenticación devueltos por el WSAA.
    """
    token: str
    sign: str
    cuit: str
    expires_at: datetime

    def is_expired(self, margin_seconds: int = 60) -> bool:
        now = datetime.now(self.expires_at.tzinfo)
        return now + timedelta(seconds=margin_seconds) >= self.expires_at


# ======================================================================
# CONFIGURACIÓN ARCA (desde settings)
# ======================================================================

class ArcaConfig:
    def __init__(self) -> None:
        env = settings.ARCA_ENV

        if env == "PRODUCCION":
            self.mode = "PRODUCCION"
            self.cuit = settings.ARCA_PROD_CUIT
            self.cert_path = Path(settings.ARCA_PROD_CERT_PATH)
            self.key_path = Path(settings.ARCA_PROD_KEY_PATH)
            self.key_password = settings.ARCA_PROD_KEY_PASSWORD
            self.wsaa_url = "https://wsaa.afip.gov.ar/ws/services/LoginCms"

        elif env == "HOMOLOGACION":
            self.mode = "HOMOLOGACION"
            self.cuit = settings.ARCA_HOMO_CUIT
            self.cert_path = Path(settings.ARCA_HOMO_CERT_PATH)
            self.key_path = Path(settings.ARCA_HOMO_KEY_PATH)
            self.key_password = settings.ARCA_HOMO_KEY_PASSWORD
            self.wsaa_url = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"

        else:
            raise ValueError(f"ARCA environment inválido: {env}")

            
        


# ======================================================================
# CLIENTE WSAA
# ======================================================================

class ArcaWSAAClient:
    SERVICE_NAME = "wsfe"

    def __init__(self, config: Optional[ArcaConfig] = None) -> None:
        self._config = config or ArcaConfig()
        self._cached_auth: Optional[ArcaAuthData] = None
        print(self._config.mode)
        suffix = "prod" if self._config.mode == "PRODUCCION" else "homo"
        self.TA_PATH = Path(settings.APP_DATA_DIR) / f"arca_ta_{suffix}.xml"

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_auth(self, force_renew: bool = False) -> ArcaAuthData:
        if not force_renew and self._cached_auth and not self._cached_auth.is_expired():
            return self._cached_auth

        if not force_renew:
            ta_disk = self._load_ta_from_disk()
            if ta_disk and not ta_disk.is_expired():
                self._cached_auth = ta_disk
                return ta_disk

        auth = self._request_new_ticket()
        self._cached_auth = auth
        self._save_ta_to_disk(auth)
        return auth

    # ------------------------------------------------------------------
    # Cache en disco
    # ------------------------------------------------------------------

    def _load_ta_from_disk(self) -> Optional[ArcaAuthData]:
        if not self.TA_PATH.exists():
            return None

        try:
            root = ET.fromstring(self.TA_PATH.read_text(encoding="utf-8"))
            token = root.findtext("token")
            sign = root.findtext("sign")
            exp = root.findtext("expires_at")

            if not token or not sign or not exp:
                return None

            return ArcaAuthData(
                token=token,
                sign=sign,
                cuit=self._config.cuit,
                expires_at=datetime.fromisoformat(exp),
            )
        except Exception:
            return None

    def _save_ta_to_disk(self, auth: ArcaAuthData) -> None:
        xml = f"""<TA>
  <token>{auth.token}</token>
  <sign>{auth.sign}</sign>
  <expires_at>{auth.expires_at.isoformat()}</expires_at>
</TA>
"""
        self.TA_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.TA_PATH.write_text(xml, encoding="utf-8")

    # ------------------------------------------------------------------
    # Flujo WSAA
    # ------------------------------------------------------------------

    def _request_new_ticket(self) -> ArcaAuthData:
        ltr_xml = self._build_login_ticket_request()
        cms_b64 = self._sign_with_openssl(ltr_xml)
        resp_xml = self._call_wsaa(cms_b64)
        return self._parse_login_ticket_response(resp_xml)

    def _build_login_ticket_request(self) -> str:
        now = datetime.now(ARG)
        gen = now - timedelta(minutes=5)
        exp = now + timedelta(hours=12)
        uid = int(now.timestamp())

        def fmt(dt: datetime) -> str:
            s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
            return s[:-2] + ":" + s[-2:]

        root = ET.Element("loginTicketRequest", version="1.0")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "uniqueId").text = str(uid)
        ET.SubElement(header, "generationTime").text = fmt(gen)
        ET.SubElement(header, "expirationTime").text = fmt(exp)
        ET.SubElement(root, "service").text = self.SERVICE_NAME

        return ET.tostring(root, encoding="utf-8").decode()

    def _sign_with_openssl(self, xml: str) -> str:
        if not self._config.cert_path.exists():
            raise FileNotFoundError(f"Certificado ARCA no encontrado: {self._config.cert_path}")
        if not self._config.key_path.exists():
            raise FileNotFoundError(f"Clave privada ARCA no encontrada: {self._config.key_path}")

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".xml", encoding="utf-8") as f:
            f.write(xml)
            xml_path = f.name

        try:
            cmd = [
                str(get_openssl_path()), "smime", "-sign",
                "-signer", str(self._config.cert_path),
                "-inkey", str(self._config.key_path),
                "-outform", "DER",
                "-nodetach",
                "-noattr",
                "-in", xml_path,
            ]
            if self._config.key_password:
                cmd.extend(["-passin", f"pass:{self._config.key_password}"])

            proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return base64.b64encode(proc.stdout).decode()
        finally:
            try:
                Path(xml_path).unlink()
            except Exception:
                pass

    def _call_wsaa(self, cms_b64: str) -> str:
        soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov">
  <soapenv:Body>
    <wsaa:loginCms>
      <wsaa:in0>{cms_b64}</wsaa:in0>
    </wsaa:loginCms>
  </soapenv:Body>
</soapenv:Envelope>
"""
        req = urllib.request.Request(
            self._config.wsaa_url,
            data=soap.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "\"loginCms\"",
            },
            method="POST",
        )
        

        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Error WSAA HTTP {e.code}: {e.read().decode(errors='ignore')}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"No se pudo conectar al WSAA: {e}") from e

    def _parse_login_ticket_response(self, xml: str) -> ArcaAuthData:
        root = ET.fromstring(xml)

        login_return = None
        for el in root.iter():
            if el.tag.endswith("loginCmsReturn") and el.text:
                login_return = el.text.strip()
                break

        if not login_return:
            raise RuntimeError("No se encontró loginCmsReturn en WSAA")

        ltr = ET.fromstring(login_return)

        def find(tag: str) -> str:
            for el in ltr.iter():
                if el.tag.endswith(tag) and el.text:
                    return el.text.strip()
            raise RuntimeError(f"Falta tag {tag} en LoginTicketResponse")

        token = find("token")
        sign = find("sign")
        exp = find("expirationTime")

        return ArcaAuthData(
            token=token,
            sign=sign,
            cuit=self._config.cuit,
            expires_at=datetime.fromisoformat(exp),
        )
