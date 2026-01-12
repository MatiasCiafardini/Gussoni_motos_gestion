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
        interes_pct: float | None = None,
        anticipo: float | None = None,
        cantidad_cuotas: int | None = None,
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
        interes_pct = interes_pct or 0.0

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

        # -------- Financiación --------
        if forma_pago_id == 3:
            if not cantidad_cuotas or cantidad_cuotas <= 0:
                raise ValueError("Cantidad de cuotas inválida")

            monto_base = precio_total - anticipo
            if monto_base <= 0:
                raise ValueError("El monto financiado debe ser mayor a 0")

            if interes_pct < 0:
                raise ValueError("El interés no puede ser negativo")

            total_financiado = monto_base * (1 + interes_pct / 100)

            plan_id = db.execute(
                text("""
                    INSERT INTO plan_financiacion
                    (venta_id, cantidad_cuotas, fecha_inicio, monto_financiado, interes_pct)
                    VALUES
                    (:venta_id, :cuotas, :fecha, :monto, :interes)
                """),
                {
                    "venta_id": venta_id,
                    "cuotas": cantidad_cuotas,
                    "fecha": fecha_inicio,
                    "monto": total_financiado,
                    "interes": interes_pct,
                }
            ).lastrowid

            importe_cuota = round(total_financiado / cantidad_cuotas, 2)

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
                        "fecha": fecha_inicio,
                        "mes": nro,
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
