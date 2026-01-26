from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class ArcaEnv:
    ENV = os.getenv("ARCA_ENV", "PROD").upper()  # HOMO o PROD
    IS_PROD = ENV in ("PROD", "PRODUCCION")

    # CUIT EMISOR (EMPRESA)
    CUIT = "33717057479"
    #20240620988 <-- es el personal.
    CERT_DIR = BASE_DIR / "app/certificados"

    if IS_PROD:
        CERT = CERT_DIR / "prod.crt"
        KEY = CERT_DIR / "prod.key"

        WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
        WSFE_URL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"
    else:
        CERT = CERT_DIR / "homo.crt"
        KEY = CERT_DIR / "homo.key"

        WSAA_URL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
        WSFE_URL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
