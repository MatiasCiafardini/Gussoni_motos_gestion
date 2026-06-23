from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.integrations.arca.wsfe_client import ArcaWSFEResult


@dataclass
class FakeAuth:
    token: str = "TOKEN_TEST"
    sign: str = "SIGN_TEST"
    cuit: str = "33717057479"


class FakeWSAA:
    def get_auth(self) -> FakeAuth:
        return FakeAuth()


class FakeWSFE:
    def __init__(
        self,
        *,
        ultimo_autorizado: int = 0,
        aprobada: bool = True,
        cae: str = "71234567890123",
        vto_cae: str = "20301231",
        errores: Optional[List[str]] = None,
    ) -> None:
        self.ultimo_autorizado = ultimo_autorizado
        self.aprobada = aprobada
        self.cae = cae
        self.vto_cae = vto_cae
        self.errores = errores or ["10016 - Rechazo de prueba"]
        self.solicitudes: List[Dict[str, Any]] = []

    def fe_comp_ultimo_autorizado(self, *, auth: Any, cbte_tipo: int, pto_vta: int) -> Dict[str, int]:
        return {"cbte_nro": self.ultimo_autorizado}

    def solicitar_cae(self, *, auth: Any, factura: Dict[str, Any], items: List[Dict[str, Any]]) -> ArcaWSFEResult:
        self.solicitudes.append({"factura": dict(factura), "items": list(items)})
        if self.aprobada:
            numero = int(factura.get("numero") or self.ultimo_autorizado + 1)
            self.ultimo_autorizado = max(self.ultimo_autorizado, numero)
            return ArcaWSFEResult(
                aprobada=True,
                rechazada=False,
                cae=self.cae,
                fecha_cae=None,
                vto_cae=self.vto_cae,
                errores=[],
                observaciones=[],
                mensaje=f"Resultado: A - CAE: {self.cae} - Vto CAE: {self.vto_cae}",
            )

        return ArcaWSFEResult(
            aprobada=False,
            rechazada=True,
            cae=None,
            fecha_cae=None,
            vto_cae=None,
            errores=self.errores,
            observaciones=[],
            mensaje="Resultado: R - Errores: " + "; ".join(self.errores),
        )


class FakeWSFEConError(FakeWSFE):
    def __init__(self, mensaje: str = "Timeout ARCA de prueba") -> None:
        super().__init__(ultimo_autorizado=0, aprobada=False)
        self.mensaje = mensaje

    def solicitar_cae(self, *, auth: Any, factura: Dict[str, Any], items: List[Dict[str, Any]]) -> ArcaWSFEResult:
        self.solicitudes.append({"factura": dict(factura), "items": list(items)})
        raise TimeoutError(self.mensaje)
