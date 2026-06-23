-- Etapa 4 - Venta beta segura
-- Base objetivo inicial: motoagency_desarrollo
--
-- Reglas:
-- - No borra datos.
-- - No modifica datos existentes.
-- - No elimina ni renombra columnas/tablas.
-- - Solo agrega tablas nuevas para un flujo beta paralelo.

CREATE TABLE IF NOT EXISTS presupuestos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cliente_id BIGINT UNSIGNED NULL,
    usuario_id INT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'BORRADOR',
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    total DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    moneda CHAR(3) NOT NULL DEFAULT 'ARS',
    observaciones TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_presupuestos_cliente_fecha (cliente_id, fecha),
    KEY idx_presupuestos_estado_fecha (estado, fecha),
    KEY idx_presupuestos_usuario_fecha (usuario_id, fecha),
    CONSTRAINT fk_presupuestos_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    CONSTRAINT fk_presupuestos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS presupuestos_detalle (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    presupuesto_id BIGINT UNSIGNED NOT NULL,
    vehiculo_id BIGINT UNSIGNED NULL,
    descripcion VARCHAR(255) NOT NULL,
    cantidad DECIMAL(12,3) NOT NULL DEFAULT 1.000,
    precio_unitario DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    importe_total DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_presupuesto_detalle_presupuesto (presupuesto_id),
    KEY idx_presupuesto_detalle_vehiculo (vehiculo_id),
    CONSTRAINT fk_presupuesto_detalle_presupuesto
        FOREIGN KEY (presupuesto_id) REFERENCES presupuestos(id),
    CONSTRAINT fk_presupuesto_detalle_vehiculo
        FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reservas (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    presupuesto_id BIGINT UNSIGNED NULL,
    cliente_id BIGINT UNSIGNED NOT NULL,
    vehiculo_id BIGINT UNSIGNED NOT NULL,
    usuario_id INT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'ACTIVA',
    fecha_reserva DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento DATETIME NULL,
    monto_senia DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    observaciones TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_reservas_cliente_fecha (cliente_id, fecha_reserva),
    KEY idx_reservas_vehiculo_estado (vehiculo_id, estado),
    KEY idx_reservas_estado_vencimiento (estado, fecha_vencimiento),
    KEY idx_reservas_presupuesto (presupuesto_id),
    CONSTRAINT fk_reservas_presupuesto
        FOREIGN KEY (presupuesto_id) REFERENCES presupuestos(id),
    CONSTRAINT fk_reservas_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    CONSTRAINT fk_reservas_vehiculo
        FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
    CONSTRAINT fk_reservas_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
