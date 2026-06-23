from __future__ import annotations


class EstadoFactura:
    BORRADOR = 12
    PENDIENTE_AFIP = 13
    AUTORIZADA = 14
    RECHAZADA = 15
    ANULADA = 16
    ERROR_COMUNICACION = 18
    PAGADA = 22


class EstadoVenta:
    BORRADOR = 30
    ACTIVA = 31
    CERRADA = 32
    CANCELADA = 33


class EstadoStock:
    DISPONIBLE = 1
    RESERVADO = 2
    VENDIDO = 3


class TipoMovimientoStock:
    INGRESO = "INGRESO"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    RESERVA = "RESERVA"
    VENTA = "VENTA"
    REMITO = "REMITO"
    ANULACION = "ANULACION"


class EstadoPresupuesto:
    BORRADOR = "BORRADOR"
    ENVIADO = "ENVIADO"
    APROBADO = "APROBADO"
    CANCELADO = "CANCELADO"
    VENCIDO = "VENCIDO"


class EstadoReserva:
    ACTIVA = "ACTIVA"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    VENCIDA = "VENCIDA"


class FormaPago:
    FINANCIACION = 3


class RolUsuario:
    ADMIN = "admin"
    VENDEDOR = "vendedor"
