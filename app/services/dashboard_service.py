from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.repositories.vehiculos_repository import VehiculosRepository
from app.repositories.ventas_repository import VentasRepository

@dataclass
class DashboardData:
    ventas_mes_cantidad: int
    ventas_mes_total: float
    stock_total: int
    stock_disponible: int
    stock_por_estado: list
    top_marcas: list
    ultimas_ventas: list

class DashboardService:
    def __init__(self, db: Session):
        self.vehiculos_repo = VehiculosRepository(db)
        self.ventas_repo = VentasRepository(db)

    def load_dashboard(self) -> DashboardData:
        ventas_mes = self.ventas_repo.metrics_mes_actual()
        return DashboardData(
            ventas_mes_cantidad=ventas_mes["cantidad"],
            ventas_mes_total=ventas_mes["total"],
            stock_total=self.vehiculos_repo.count_all(),
            stock_disponible=self.vehiculos_repo.count_disponibles(),
            stock_por_estado=self.vehiculos_repo.stock_por_estado(),
            top_marcas=self.vehiculos_repo.top_marcas(limit=6),
            ultimas_ventas=self.ventas_repo.ultimas(limit=6),
        )
