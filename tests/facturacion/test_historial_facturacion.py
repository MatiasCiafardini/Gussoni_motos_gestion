from datetime import datetime

from sqlalchemy import text

from app.repositories.vehiculos_repository import VehiculosRepository
from app.services.ventas_service import VentasService
from tests.fixtures.db_factory import insert_factura_autorizada


def _agregar_moto_a_factura(db, factura_id: int, vehiculo_id: int, importe: float = 500.0):
    db.execute(
        text(
            """
            INSERT INTO facturas_detalle
            (factura_id,item_tipo,vehiculo_id,descripcion,cantidad,precio_unitario,
             alicuota_iva,importe_neto,importe_iva,importe_total)
            VALUES (:factura,'VEHICULO',:vehiculo,'MOTO ADICIONAL',1,:importe,21,
                    :importe,0,:importe)
            """
        ),
        {"factura": factura_id, "vehiculo": vehiculo_id, "importe": importe},
    )
    db.commit()


def test_historial_vehiculo_conserva_reventas(db, cliente_id, vehiculo_id):
    primera = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=10)
    segunda = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=11)

    historial = VehiculosRepository(db).get_facturacion_history(vehiculo_id)

    assert [item["factura_id"] for item in historial] == [segunda, primera]
    assert all(item["cliente_id"] == cliente_id for item in historial)


def test_historial_cliente_agrupa_varias_motos_por_factura(
    db, cliente_id, vehiculo_id, make_vehiculo
):
    otra_moto = make_vehiculo(suffix="DOS")
    factura_id = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=20)
    _agregar_moto_a_factura(db, factura_id, otra_moto)

    historial = VentasService().get_facturacion_by_cliente(cliente_id)

    assert len(historial) == 1
    assert historial[0]["factura_id"] == factura_id
    assert "CUADRO-1" in historial[0]["descripcion"]
    assert "CUADRO-DOS" in historial[0]["descripcion"]
    assert historial[0]["comprobante"].endswith("00002-00000020")
