from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from typing import Any, Dict

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def make_sqlite_sessionmaker(tmp_path: Path):
    sqlite3.register_adapter(Decimal, float)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _register_functions(dbapi_connection, _connection_record):
        def concat_ws(separator, *args):
            return str(separator).join(str(a) for a in args if a not in (None, ""))

        def date_add(value, months):
            from datetime import datetime

            base = value
            if isinstance(base, str):
                try:
                    base = datetime.fromisoformat(base)
                except ValueError:
                    base = datetime.strptime(base[:10], "%Y-%m-%d")
            month_index = base.month - 1 + int(months or 0)
            year = base.year + month_index // 12
            month = month_index % 12 + 1
            return f"{year:04d}-{month:02d}-{min(base.day, 28):02d}"

        dbapi_connection.create_function("CONCAT_WS", -1, concat_ws)
        dbapi_connection.create_function("DATE_ADD", 2, date_add)

    SessionTesting = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with engine.begin() as conn:
        _create_schema(conn)
        _seed_catalogs(conn)
    return SessionTesting


def _create_schema(conn) -> None:
    statements = [
        """
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nro_doc TEXT NOT NULL,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            observaciones TEXT,
            estado_id INTEGER DEFAULT 10,
            tipo_doc_id INTEGER
        )
        """,
        """
        CREATE TABLE tipos_documento (
            id INTEGER PRIMARY KEY,
            codigo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            activo INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE estados (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            tipo TEXT
        )
        """,
        """
        CREATE TABLE estados_stock (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            descripcion TEXT
        )
        """,
        """
        CREATE TABLE colores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            codigo_hex TEXT,
            descripcion TEXT
        )
        """,
        """
        CREATE TABLE forma_pago (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            descripcion TEXT
        )
        """,
        """
        CREATE TABLE proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE puntos_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            punto_venta INTEGER NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE tipos_comprobante (
            id INTEGER PRIMARY KEY,
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            letra TEXT NOT NULL,
            es_nota_credito INTEGER DEFAULT 0,
            es_nota_debito INTEGER DEFAULT 0,
            activo INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            anio INTEGER,
            nro_certificado TEXT,
            nro_dnrpa TEXT,
            lca TEXT,
            numero_cuadro TEXT UNIQUE,
            numero_motor TEXT UNIQUE,
            precio_lista NUMERIC NOT NULL DEFAULT 0,
            color_id INTEGER,
            estado_stock_id INTEGER NOT NULL,
            estado_moto_id INTEGER NOT NULL,
            proveedor_id INTEGER,
            observaciones TEXT,
            cliente_id INTEGER
        )
        """,
        """
        CREATE TABLE ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATETIME NOT NULL,
            vehiculo_id INTEGER NOT NULL,
            cliente_id INTEGER NOT NULL,
            precio_total NUMERIC,
            anticipo NUMERIC,
            forma_pago_id INTEGER,
            observaciones TEXT,
            estado_id INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_origen_id INTEGER,
            tipo_comprobante_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            fecha_emision DATETIME NOT NULL,
            punto_venta INTEGER NOT NULL,
            moneda TEXT DEFAULT 'ARS',
            cotizacion NUMERIC DEFAULT 1,
            cae TEXT,
            fecha_cae TEXT,
            vto_cae TEXT,
            subtotal NUMERIC DEFAULT 0,
            iva NUMERIC DEFAULT 0,
            total NUMERIC DEFAULT 0,
            observaciones TEXT,
            estado_id INTEGER,
            cliente_id INTEGER,
            condicion_iva_receptor_id INTEGER,
            venta_id INTEGER,
            cbte_asoc_tipo TEXT,
            cbte_asoc_pto_vta INTEGER,
            cbte_asoc_numero INTEGER,
            UNIQUE(tipo_comprobante_id, punto_venta, numero)
        )
        """,
        """
        CREATE TABLE facturas_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            item_tipo TEXT,
            vehiculo_id INTEGER,
            descripcion TEXT,
            cantidad NUMERIC,
            precio_unitario NUMERIC,
            alicuota_iva NUMERIC,
            importe_neto NUMERIC,
            importe_iva NUMERIC,
            importe_total NUMERIC
        )
        """,
        """
        CREATE TABLE stock_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehiculo_id INTEGER,
            estado_stock_anterior_id INTEGER,
            estado_stock_nuevo_id INTEGER,
            tipo_movimiento TEXT,
            origen_tipo TEXT,
            origen_id INTEGER,
            usuario_id INTEGER,
            observaciones TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidad TEXT NOT NULL,
            entidad_id INTEGER,
            accion TEXT NOT NULL,
            usuario_id INTEGER,
            datos_previos TEXT,
            datos_nuevos TEXT,
            contexto TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE plan_financiacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER UNIQUE,
            cantidad_cuotas INTEGER,
            importe_cuota NUMERIC,
            fecha_inicio DATETIME,
            monto_financiado NUMERIC
        )
        """,
        """
        CREATE TABLE cuotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            nro_cuota INTEGER,
            monto NUMERIC,
            monto_pagado NUMERIC DEFAULT 0,
            fecha_vencimiento TEXT,
            estado TEXT DEFAULT 'PENDIENTE'
        )
        """,
        """
        CREATE TABLE pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATETIME,
            venta_id INTEGER,
            cliente_id INTEGER,
            monto NUMERIC,
            forma_pago_id INTEGER,
            observaciones TEXT
        )
        """,
        """
        CREATE TABLE pagos_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pago_id INTEGER,
            cuota_id INTEGER,
            monto_aplicado NUMERIC
        )
        """,
    ]
    for statement in statements:
        conn.execute(text(statement))


def _seed_catalogs(conn) -> None:
    conn.execute(
        text("INSERT INTO tipos_documento (id, codigo, descripcion) VALUES (80,'CUIT','CUIT'),(96,'DNI','DNI')")
    )
    conn.execute(
        text(
            """
            INSERT INTO estados (id, nombre, tipo) VALUES
            (1,'Nueva','vehiculos'),
            (10,'Activo','clientes'),
            (12,'Borrador','facturas'),
            (13,'Pendiente AFIP','facturas'),
            (14,'Autorizada','facturas'),
            (15,'Rechazada','facturas'),
            (16,'Anulada','facturas'),
            (18,'Error Comunicación','facturas'),
            (30,'Abierta','ventas'),
            (31,'Activa','ventas'),
            (32,'Cerrada','ventas'),
            (33,'Cancelada','ventas')
            """
        )
    )
    conn.execute(
        text("INSERT INTO estados_stock (id,nombre) VALUES (1,'Disponible'),(2,'Reservado'),(3,'Vendido'),(4,'Baja')")
    )
    conn.execute(
        text("INSERT INTO colores (id,nombre) VALUES (1,'Negro'),(2,'Blanco'),(3,'Rojo'),(4,'Azul')")
    )
    conn.execute(
        text("INSERT INTO forma_pago (id,nombre) VALUES (1,'Efectivo'),(2,'Transferencia'),(3,'Financiación')")
    )
    conn.execute(text("INSERT INTO proveedores (id,razon_social) VALUES (1,'Proveedor QA')"))
    conn.execute(text("INSERT INTO puntos_venta (id,punto_venta) VALUES (1,1),(2,2)"))
    conn.execute(
        text(
            """
            INSERT INTO tipos_comprobante
            (id,codigo,nombre,letra,es_nota_credito,es_nota_debito,activo) VALUES
            (1,'FA','Factura A','A',0,0,1),
            (2,'FB','Factura B','B',0,0,1),
            (3,'FC','Factura C','C',0,0,1),
            (4,'NCA','Nota de Crédito A','A',1,0,1),
            (5,'NCB','Nota de Crédito B','B',1,0,1),
            (6,'NCC','Nota de Crédito C','C',1,0,1)
            """
        )
    )


def insert_cliente(db, **overrides: Any) -> int:
    data: Dict[str, Any] = {
        "nro_doc": "95083105",
        "nombre": "Cliente",
        "apellido": "QA",
        "telefono": "111",
        "email": "qa@example.com",
        "direccion": "Calle QA",
        "estado_id": 10,
        "tipo_doc_id": 96,
    }
    data.update(overrides)
    result = db.execute(
        text(
            """
            INSERT INTO clientes
            (nro_doc,nombre,apellido,telefono,email,direccion,estado_id,tipo_doc_id)
            VALUES (:nro_doc,:nombre,:apellido,:telefono,:email,:direccion,:estado_id,:tipo_doc_id)
            """
        ),
        data,
    )
    db.commit()
    return int(result.lastrowid)


def insert_vehiculo(db, **overrides: Any) -> int:
    suffix = overrides.pop("suffix", "1")
    data: Dict[str, Any] = {
        "marca": "QA",
        "modelo": "MOTO TEST",
        "anio": 2026,
        "nro_certificado": f"CERT-{suffix}",
        "nro_dnrpa": f"DNRPA-{suffix}",
        "lca": "IF-2024-117060280-APN-SSAM#JGM",
        "numero_cuadro": f"CUADRO-{suffix}",
        "numero_motor": f"MOTOR-{suffix}",
        "precio_lista": 1000,
        "color_id": 1,
        "estado_stock_id": 1,
        "estado_moto_id": 1,
        "observaciones": None,
    }
    data.update(overrides)
    result = db.execute(
        text(
            """
            INSERT INTO vehiculos
            (marca,modelo,anio,nro_certificado,nro_dnrpa,lca,numero_cuadro,numero_motor,
             precio_lista,color_id,estado_stock_id,estado_moto_id,observaciones)
            VALUES
            (:marca,:modelo,:anio,:nro_certificado,:nro_dnrpa,:lca,:numero_cuadro,:numero_motor,
             :precio_lista,:color_id,:estado_stock_id,:estado_moto_id,:observaciones)
            """
        ),
        data,
    )
    db.commit()
    return int(result.lastrowid)


def insert_factura_autorizada(db, cliente_id: int, vehiculo_id: int, *, numero: int = 1) -> int:
    venta = db.execute(
        text(
            """
            INSERT INTO ventas (fecha,cliente_id,vehiculo_id,precio_total,anticipo,forma_pago_id,estado_id)
            VALUES (:fecha,:cliente,:vehiculo,1000,0,1,31)
            """
        ),
        {"fecha": datetime.now(), "cliente": cliente_id, "vehiculo": vehiculo_id},
    )
    venta_id = int(venta.lastrowid)
    factura = db.execute(
        text(
            """
            INSERT INTO facturas
            (tipo_comprobante_id,numero,fecha_emision,punto_venta,subtotal,iva,total,estado_id,cliente_id,condicion_iva_receptor_id,venta_id,cae,vto_cae)
            VALUES (2,:numero,:fecha,2,826.45,173.55,1000,14,:cliente,5,:venta,'CAE-ORIG','20301231')
            """
        ),
        {"numero": numero, "fecha": datetime.now(), "cliente": cliente_id, "venta": venta_id},
    )
    factura_id = int(factura.lastrowid)
    db.execute(
        text(
            """
            INSERT INTO facturas_detalle
            (factura_id,item_tipo,vehiculo_id,descripcion,cantidad,precio_unitario,alicuota_iva,importe_neto,importe_iva,importe_total)
            VALUES (:factura,'VEHICULO',:vehiculo,'QA MOTO TEST',1,1000,21,826.45,173.55,1000)
            """
        ),
        {"factura": factura_id, "vehiculo": vehiculo_id},
    )
    db.execute(text("UPDATE vehiculos SET estado_stock_id=3 WHERE id=:id"), {"id": vehiculo_id})
    db.commit()
    return factura_id
