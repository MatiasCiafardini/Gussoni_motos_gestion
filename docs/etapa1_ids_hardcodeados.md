# Etapa 1 - IDs hardcodeados pendientes

Este inventario deja marcados los valores que no se migran en Etapa 1 para no tocar
flujos grandes ni datos existentes. La Etapa 1 solo introduce constantes centrales y
reemplaza usos de bajo riesgo fuera de `FacturasService`.

## Pendientes intencionales

- `app/services/facturas_service.py`: mantiene IDs internos de estados de factura,
  venta cancelada y stock disponible. Se difiere hasta separar servicios de
  facturacion, ARCA, venta y stock.
- `app/ui/pages/facturas_agregar.py`: mantiene `forma_pago_id == 3` en la pantalla
  actual. Se difiere hasta crear el flujo beta de venta.
- `app/ui/pages/dashboard_page.py`: mantiene `estado_id = 12` mientras el dashboard
  siga consultando SQL directo desde UI.
- `app/repositories/clientes_repository.py`: mantiene `10/11` como fallback visual
  de estados de cliente. Se debe reemplazar por catalogo de estados de cliente.
- `app/services/pagos_service.py`: mantiene `ESTADO_FACTURA_PENDIENTE = 21` porque
  no se usa en el flujo actual revisado; se debe confirmar contra catalogo real.

## Ya centralizado en Etapa 1

- Estados de venta usados por `VentasService`.
- Estado de factura pagada usado por `PagosService`.
- Estados de stock usados por `RemitosService`.
- Forma de pago financiacion usada por `VentasService`.
- Estados de venta usados por `DashboardService`.
