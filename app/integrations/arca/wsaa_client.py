from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import base64
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from app.core.config import settings

ARG = timezone(timedelta(hours=-3))


def _der_tlv(tag: bytes, value: bytes) -> bytes:
    n = len(value)
    if n < 128:
        return tag + bytes([n]) + value
    elif n < 256:
        return tag + b'\x81' + bytes([n]) + value
    elif n < 65536:
        return tag + b'\x82' + bytes([n >> 8, n & 0xFF]) + value
    raise OverflowError(f"DER value too long: {n}")


def _der_oid(s: str) -> bytes:
    parts = [int(x) for x in s.split('.')]
    body = bytes([40 * parts[0] + parts[1]])
    for v in parts[2:]:
        if v == 0:
            body += b'\x00'
        else:
            chunks: list[int] = []
            while v:
                chunks.append(v & 0x7F)
                v >>= 7
            chunks.reverse()
            for i, c in enumerate(chunks):
                body += bytes([c | 0x80 if i < len(chunks) - 1 else c])
    return _der_tlv(b'\x06', body)


def _build_pkcs7_signed_data(
    data: bytes,
    cert_der: bytes,
    issuer_der: bytes,
    serial_bytes: bytes,
    signature: bytes,
) -> bytes:
    """
    Builds a PKCS7 SignedData (DER) with IssuerAndSerialNumber (v1 signerInfo).
    Pure Python — does not rely on OpenSSL's PKCS7/CMS signer-identifier logic.
    No signed attributes (equivalent to openssl smime -noattr).
    """
    def seq(*p): return _der_tlv(b'\x30', b''.join(p))
    def set_(*p): return _der_tlv(b'\x31', b''.join(p))
    def ctx(n, *p): return _der_tlv(bytes([0xA0 | n]), b''.join(p))
    def octet(b): return _der_tlv(b'\x04', b)

    NULL = b'\x05\x00'
    sha256_alg = seq(_der_oid('2.16.840.1.101.3.4.2.1'), NULL)
    rsa_alg    = seq(_der_oid('1.2.840.113549.1.1.1'), NULL)

    encap_content = seq(_der_oid('1.2.840.113549.1.7.1'), ctx(0, octet(data)))
    issuer_and_serial = seq(issuer_der, _der_tlv(b'\x02', serial_bytes))

    signer_info = seq(
        b'\x02\x01\x01',     # version 1
        issuer_and_serial,
        sha256_alg,           # digestAlgorithm
        # no signed attributes
        rsa_alg,              # digestEncryptionAlgorithm
        octet(signature),     # encryptedDigest
    )

    signed_data = seq(
        b'\x02\x01\x01',     # version 1
        set_(sha256_alg),     # digestAlgorithms
        encap_content,
        ctx(0, cert_der),     # certificates [0] IMPLICIT
        set_(signer_info),    # signerInfos
    )

    return seq(_der_oid('1.2.840.113549.1.7.2'), ctx(0, signed_data))


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
        """
        Builds a PKCS7 SignedData forcing IssuerAndSerialNumber (v1 signerInfo).
        Pure Python ASN.1 construction — avoids OpenSSL 3.x SubjectKeyIdentifier default.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
        from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding
        from cryptography.x509 import load_pem_x509_certificate

        if not self._config.cert_path.exists():
            raise FileNotFoundError(f"Certificado ARCA no encontrado: {self._config.cert_path}")
        if not self._config.key_path.exists():
            raise FileNotFoundError(f"Clave privada ARCA no encontrada: {self._config.key_path}")

        cert = load_pem_x509_certificate(self._config.cert_path.read_bytes())
        password = self._config.key_password.encode() if self._config.key_password else None
        private_key = load_pem_private_key(self._config.key_path.read_bytes(), password=password)

        data = xml.encode("utf-8")
        cert_der = cert.public_bytes(Encoding.DER)

        # Sign raw data — no signed attributes (like smime -noattr)
        signature = private_key.sign(data, asym_padding.PKCS1v15(), hashes.SHA256())

        issuer_der = cert.issuer.public_bytes()
        sn = cert.serial_number
        sn_bytes = sn.to_bytes(max(1, (sn.bit_length() + 7) // 8), 'big')
        if sn_bytes[0] & 0x80:
            sn_bytes = b'\x00' + sn_bytes

        pkcs7_der = _build_pkcs7_signed_data(data, cert_der, issuer_der, sn_bytes, signature)
        return base64.b64encode(pkcs7_der).decode()

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
