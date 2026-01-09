from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class ArcaEnv:
    ENV = os.getenv("ARCA_ENV", "HOMO").upper() #poner HOMO para simulacion y PROD para produccion

    IS_PROD = ENV in ("PROD", "PRODUCCION")

    CUIT = "20240620988"

    if IS_PROD:
        CERT = BASE_DIR / "certs" / "gussoni_prod.crt"
        KEY = BASE_DIR / "certs" / "gussoni_prod.key"
        WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
        WSFE_URL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"
    else:
        CERT = BASE_DIR / "certs" / "cert_homo.crt"
        KEY = BASE_DIR / "certs" / "private.key"
        WSAA_URL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
        WSFE_URL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
