# QA regresion core - 2026-06-23

Base usada: `motoagency_desarrollo`

Entorno fiscal usado: ARCA homologacion

## Validaciones ejecutadas

- Conexion a base de desarrollo.
- Existencia de tablas nuevas:
  - `stock_movimientos`
  - `audit_log`
  - `presupuestos`
  - `presupuestos_detalle`
  - `reservas`
- Existencia de indices seguros de etapa 2.
- Alta de vehiculos QA.
- Presupuesto beta.
- Reserva beta.
- Remito emitido y anulado.
- Factura B punto de venta 2.
- Autorizacion ARCA homologacion.
- Rechazo ARCA y reversa de efectos comerciales.
- Auditoria y movimientos de stock.

## Datos QA creados

- Vehiculos QA: `658`, `659`, `660`.
- Presupuesto beta: `1`.
- Reserva beta: `1`.
- Remito: `3`.
- Factura B QA: `295`, punto de venta `2`, numero `57`.
- Venta asociada: `148`.

## Hallazgos

### Numeracion AFIP/local desfasada

ARCA homologacion informo ultimo autorizado B/PV2 `22`, por lo que esperaba el numero `23`.
La base local clonada tenia facturas B/PV2 hasta el numero `56`.

Se corrigio `FacturaNumberingService` para calcular el proximo numero como el mayor entre:

- proximo AFIP
- proximo local

Esto evita duplicados locales en bases clonadas.

### Rechazo ARCA dejaba venta y stock activos

Antes del ajuste, si ARCA rechazaba una factura, el vehiculo quedaba vendido y la venta activa.

Se agrego `FacturaRejectionService` para que, ante rechazo definitivo de ARCA:

- la factura quede rechazada
- la venta asociada quede cancelada
- el vehiculo vuelva a disponible
- se registre movimiento de stock
- se registre auditoria

### FacturasRepository no exponia estados de factura

`FacturasService` llamaba `list_estados_facturas()`, pero el repositorio no tenia ese metodo.
Se agrego el metodo y se hizo tolerante el cache de catalogos.

## Estado final validado

- Factura QA `295`: estado `15` (Rechazada).
- Venta QA `148`: estado `33` (Cancelada).
- Vehiculo QA `658`: estado stock `1` (Disponible).
- `stock_movimientos`: incluye ingreso, venta y anulacion por rechazo.
- `audit_log`: incluye creacion de factura, autorizacion ARCA y reversa de efectos.

## Limitacion pendiente

No se pudo obtener CAE aprobado para una factura nueva B/PV2 porque la base local clonada esta desfasada contra el contador real de ARCA homologacion.

Para probar aprobacion fiscal punta a punta se necesita:

- una base QA sin comprobantes productivos clonados para el tipo/PV usado, o
- un punto de venta homologatorio limpio y alineado con ARCA.

## Verificaciones tecnicas

- `python -m compileall -q app`: OK.
- `git diff --check`: OK, solo warnings LF/CRLF.
- `python -m pytest app/tests`: no ejecutado porque `pytest` no esta instalado en el entorno.
