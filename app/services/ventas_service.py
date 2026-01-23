from datetime import datetime
from sqlalchemy import text
from app.data.database import SessionLocal


class VentasService:

    # =========================
    # CREAR / COMPLETAR VENTA
    # =========================
        # =========================
    # CREAR VENTA BASE
    # =========================
    def crear_venta(
        self,
        *,
        db,
        cliente_id: int,
        vehiculo_id: int | None,
        fecha: datetime | None = None,
        precio_total: float = 0.0,
    ) -> int:
        """
        Crea la venta base asociada a una factura.
        NO hace commit: la transacción la controla el caller.
        """
    
        if not fecha:
            fecha = datetime.now()
    
        venta_id = db.execute(
            text("""
                INSERT INTO ventas
                (fecha, cliente_id, vehiculo_id, precio_total, estado_id)
                VALUES
                (:fecha, :cliente, :vehiculo, :precio, 30)
            """),
            {
                "fecha": fecha,
                "cliente": cliente_id,
                "vehiculo": vehiculo_id,
                "precio": precio_total,
            }
        ).lastrowid
    
        if not venta_id:
            raise RuntimeError("No se pudo crear la venta")
    
        return venta_id
    

    def completar_venta(
        self,
        *,
        db,
        venta_id: int,
        precio_total: float,
        forma_pago_id: int,
        anticipo: float | None = None,
        cantidad_cuotas: int | None = None,
        importe_cuota: float | None = None,
        fecha_inicio: datetime | None = None,
    ):
        """
        Completa los datos comerciales de una venta.
        Debe ejecutarse SIEMPRE, haya o no financiación.
        """

        if precio_total <= 0:
            raise ValueError("El precio real debe ser mayor a 0")

        if not fecha_inicio:
            fecha_inicio = datetime.now()

        anticipo = anticipo or 0.0
        importe_cuota = importe_cuota or 0.0

        # -------- Actualizar venta --------
        db.execute(
            text("""
                UPDATE ventas
                SET precio_total = :precio,
                    forma_pago_id = :forma_pago,
                    anticipo = :anticipo,
                    estado_id = 31
                WHERE id = :venta_id
            """),
            {
                "precio": precio_total,
                "forma_pago": forma_pago_id,
                "anticipo": anticipo,
                "venta_id": venta_id,
            }
        )

        if forma_pago_id == 3:
            if not cantidad_cuotas or cantidad_cuotas <= 0:
                raise ValueError("Cantidad de cuotas inválida")

            if not importe_cuota or importe_cuota <= 0:
                raise ValueError("Importe de cuota inválido")

            monto_financiado = cantidad_cuotas * importe_cuota

            plan_id = db.execute(
                text("""
                    INSERT INTO plan_financiacion
                    (venta_id, cantidad_cuotas, importe_cuota, fecha_inicio, monto_financiado)
                    VALUES
                    (:venta_id, :cuotas, :importe_cuota, :fecha, :monto)
                """),
                {
                    "venta_id": venta_id,
                    "cuotas": cantidad_cuotas,
                    "importe_cuota": importe_cuota,
                    "fecha": fecha_inicio,
                    "monto": monto_financiado,
                }
            ).lastrowid

            for nro in range(1, cantidad_cuotas + 1):
                db.execute(
                    text("""
                        INSERT INTO cuotas
                        (plan_id, nro_cuota, fecha_vencimiento, monto)
                        VALUES
                        (:plan, :nro, DATE_ADD(:fecha, INTERVAL :mes MONTH), :importe)
                    """),
                    {
                        "plan": plan_id,
                        "nro": nro,
                        "mes": nro,
                        "fecha": fecha_inicio,
                        "importe": importe_cuota,
                    }
                )



    # =========================
    # REGISTRAR PAGO
    # =========================

    def registrar_pago(
        self,
        *,
        venta_id: int,
        cliente_id: int,
        monto: float,
        forma_pago_id: int,
        observaciones: str | None = None,
    ):
        """
        Registra un pago y lo aplica automáticamente a cuotas (FIFO).
        """

        if monto <= 0:
            raise ValueError("El monto del pago debe ser mayor a 0")

        db = SessionLocal()
        try:
            pago_id = db.execute(
                text("""
                    INSERT INTO pagos
                    (fecha, venta_id, cliente_id, monto, forma_pago_id, observaciones)
                    VALUES
                    (NOW(), :venta, :cliente, :monto, :forma, :obs)
                """),
                {
                    "venta": venta_id,
                    "cliente": cliente_id,
                    "monto": monto,
                    "forma": forma_pago_id,
                    "obs": observaciones,
                }
            ).lastrowid

            self._aplicar_pago_fifo(db, pago_id, venta_id, monto)

            self._actualizar_estado_venta(db, venta_id)

            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # =========================
    # APLICAR PAGO FIFO
    # =========================

    def _aplicar_pago_fifo(self, db, pago_id, venta_id, monto):
        restante = monto

        cuotas = db.execute(
            text("""
                SELECT c.id, c.monto, c.monto_pagado
                FROM cuotas c
                JOIN plan_financiacion p ON p.id = c.plan_id
                WHERE p.venta_id = :venta
                  AND c.estado != 'PAGADA'
                ORDER BY c.fecha_vencimiento ASC, c.id ASC
            """),
            {"venta": venta_id}
        ).mappings().all()

        for cuota in cuotas:
            if restante <= 0:
                break

            saldo = cuota["monto"] - cuota["monto_pagado"]
            aplicado = min(restante, saldo)

            db.execute(
                text("""
                    INSERT INTO pagos_detalle
                    (pago_id, cuota_id, monto_aplicado)
                    VALUES
                    (:pago, :cuota, :monto)
                """),
                {
                    "pago": pago_id,
                    "cuota": cuota["id"],
                    "monto": aplicado,
                }
            )

            nuevo_pagado = cuota["monto_pagado"] + aplicado
            nuevo_estado = (
                "PAGADA" if nuevo_pagado >= cuota["monto"] else "PARCIAL"
            )

            db.execute(
                text("""
                    UPDATE cuotas
                    SET monto_pagado = :pagado,
                        estado = :estado
                    WHERE id = :id
                """),
                {
                    "pagado": nuevo_pagado,
                    "estado": nuevo_estado,
                    "id": cuota["id"],
                }
            )

            restante -= aplicado

    # =========================
    # ESTADO DE LA VENTA
    # =========================

    def _actualizar_estado_venta(self, db, venta_id):
        pendientes = db.execute(
            text("""
                SELECT COUNT(*)
                FROM cuotas c
                JOIN plan_financiacion p ON p.id = c.plan_id
                WHERE p.venta_id = :venta
                  AND c.estado != 'PAGADA'
            """),
            {"venta": venta_id}
        ).scalar()

        nuevo_estado = 32 if pendientes == 0 else 31

        db.execute(
            text("""
                UPDATE ventas
                SET estado_id = :estado
                WHERE id = :venta
            """),
            {
                "estado": nuevo_estado,
                "venta": venta_id,
            }
        )
    # =========================
    # CONSULTAS
    # =========================

    def get_by_cliente(self, cliente_id: int) -> list[dict]:
        """
        Devuelve las ventas de un cliente con estado financiero calculado.
        NO recalcula nada.
        """

        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT
                        v.id,
                        v.fecha,
                        v.precio_total,
                        v.forma_pago_id,
                        fp.nombre AS forma_pago,            

                        f.id AS factura_id,         

                        -- cuotas
                        COUNT(c.id) AS total_cuotas,
                        SUM(CASE WHEN c.estado = 'PAGADA' THEN 1 ELSE 0 END) AS cuotas_pagadas,
                        SUM(
                            CASE
                                WHEN c.estado != 'PAGADA'
                                 AND c.fecha_vencimiento < CURDATE()
                                THEN 1 ELSE 0
                            END
                        ) AS cuotas_vencidas            

                    FROM ventas v
                    LEFT JOIN forma_pago fp ON fp.id = v.forma_pago_id
                    LEFT JOIN facturas f ON f.venta_id = v.id
                    LEFT JOIN plan_financiacion p ON p.venta_id = v.id
                    LEFT JOIN cuotas c ON c.plan_id = p.id
                    WHERE v.cliente_id = :cliente
                    GROUP BY v.id, f.id
                    ORDER BY v.fecha DESC
                """),
                {"cliente": cliente_id}
            ).mappings().all()

            ventas: list[dict] = []

            for r in rows:
                # ----------------------------
                # Estado financiero calculado
                # ----------------------------
                if r["total_cuotas"] == 0:
                    estado = "PAGADA"
                elif r["cuotas_pagadas"] == r["total_cuotas"]:
                    estado = "PAGADA"
                elif r["cuotas_vencidas"] > 0:
                    estado = "CON DEUDA"
                else:
                    estado = "PENDIENTE"

                ventas.append({
                    "id": r["id"],
                    "fecha": r["fecha"],
                    "descripcion": "Venta",  # luego podés enriquecer (vehículo, etc.)
                    "precio_operacion": float(r["precio_total"]),
                    "forma_pago": r["forma_pago"],
                    "factura_id": r["factura_id"],
                    "estado_financiero": estado,
                })

            return ventas

        finally:
            db.close()
