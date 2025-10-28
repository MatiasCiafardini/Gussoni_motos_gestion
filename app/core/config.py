from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _db(name: str, default: str = "") -> str:
    # Prioriza APP_DB_* y cae a DB_*
    return os.getenv(f"APP_DB_{name}") or os.getenv(f"DB_{name}", default)

@dataclass(frozen=True)
class Settings:
    DB_HOST: str = _db("HOST", "test-desarrollo-matiasciafardini-6e07.f.aivencloud.com")
    DB_PORT: int = int(_db("PORT", "25133"))
    DB_USER: str = _db("USER", "avnadmin")
    DB_PASSWORD: str = ""
    DB_NAME: str = _db("NAME", "defaultdb")
    DB_SSL_CA: str = _db("SSL_CA", "MIIEUDCCArigAwIBAgIUeQx8ZgDeTrPKuDmPwJfCX59tEykwDQYJKoZIhvcNAQEMBQAwQDE+MDwGA1UEAww1YmE3YTFmZTAtNzQ0OC00ZDExLTllMTktNzJlOTljZDI4MjNkIEdFTiAxIFByb2plY3QgQ0EwHhcNMjUwOTEwMTI1NDE4WhcNMzUwOTA4MTI1NDE4WjBAMT4wPAYDVQQDDDViYTdhMWZlMC03NDQ4LTRkMTEtOWUxOS03MmU5OWNkMjgyM2QgR0VOIDEgUHJvamVjdCBDQTCCAaIwDQYJKoZIhvcNAQEBBQADggGPADCCAYoCggGBAKC2mTT/mBb6CnawjfVGcjQaWACXFKzhGyva87lRcnElhb95OWw0pgx01Gzhpy0cdFw7ANlIug+YpMxVhaaxQPfrU2kFKwrf3bWDChb1G5GTmpOUWEzlRpzQfWKIDGzbuQrJFpE5DgquGB6xZ+RPbjL5FFVU0QUSXAFMZpZ6cpYwnXoT+/OLDTx2/CFd65oOO5o03IXaBjWNI8gXFA+wyjBm6cfxZ497f1EZLURwBMwm/pEZxg8WMm78lcJtEV1OrXdY55a+OWsxhzOgq96Q8sHZeryauT+sX/f0OCP4kkZ+bBI817/uSK2KvMIcjBabcWwk6emoAkTLV8cRDF2mZCcCutWUBAEfBjYanQCeSYM1V8MWI/asQfZdRr+4i/CsKi75bgCy2YgndgJ3A1tM3LIUCRGLm9xwtjFJ6Sgqj5DNDttpBt6nhWVDdjSDiNi1AZg9taT56DZDkOAlygWjCPC+qZWHaRs5qqRxtNMDkUm+ApyX0akc1CS2mToWniOjOQIDAQABo0IwQDAdBgNVHQ4EFgQUGCdqupq1LjWJJGfRHGnDBFQWGEowEgYDVR0TAQH/BAgwBgEB/wIBADALBgNVHQ8EBAMCAQYwDQYJKoZIhvcNAQEMBQADggGBAE0UFGYk+ySnKjxxK8g9UxrKRqWXl2Bq6sLyHTLXZ+LaT0zbviLzLML73Hozuwkgjo2XlBtzrX2tNv74OdENh6tJU2F+j/AlgFcszxMZx2NuR4LpXVHp74mwjgIXvOANHpH0AnX6yr9k9GjO7WSnJVgjW6XTv2iIiCPdBo4QcVLuYyX0ID5gB2tA+JyLingk5XLG4obMxKovrWw88303aT1PbEH+/W843zX8FTQsbdJm9zWNU0qJXMneVzc949tRtJHZhuQpYmXpbfsbtmCMSbTTcLVMYNDJ4UabjMmcqsAqrAa4QQXqF0leL+uTGfKMB7x9chRVS+aIgQBFOSPPBDMmD74k0bQyG8epf0Bpusz2o4/HRsViobBTEsASMziPOAxs0JPJicmP3fDGGnxeYgPyo1xaJl3naOy1xIobnKwUkxCM9ZJZeuxCCbVUTguqsdSromGMZFPS68ZcL1Snl9yyYaXx6STDUBtXhR3AWSHy8qbLymGtkto1ui/TU7/Kgg==")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    APP_NAME: str = "MotoAgency Desk"

settings = Settings()
