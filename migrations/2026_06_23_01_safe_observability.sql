-- Etapa 2 - Observabilidad segura
-- Base objetivo inicial: motoagency_desarrollo
--
-- Reglas:
-- - No borra datos.
-- - No modifica datos existentes.
-- - No elimina ni renombra columnas/tablas.
-- - Solo agrega tablas nuevas e indices.

CREATE TABLE IF NOT EXISTS stock_movimientos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    vehiculo_id BIGINT UNSIGNED NOT NULL,
    estado_stock_anterior_id BIGINT UNSIGNED NULL,
    estado_stock_nuevo_id BIGINT UNSIGNED NULL,
    tipo_movimiento VARCHAR(40) NOT NULL,
    origen_tipo VARCHAR(40) NULL,
    origen_id BIGINT UNSIGNED NULL,
    usuario_id INT NULL,
    observaciones TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_stock_mov_vehiculo_fecha (vehiculo_id, created_at),
    KEY idx_stock_mov_tipo_fecha (tipo_movimiento, created_at),
    KEY idx_stock_mov_origen (origen_tipo, origen_id),
    CONSTRAINT fk_stock_mov_vehiculo
        FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
    CONSTRAINT fk_stock_mov_estado_anterior
        FOREIGN KEY (estado_stock_anterior_id) REFERENCES estados_stock(id),
    CONSTRAINT fk_stock_mov_estado_nuevo
        FOREIGN KEY (estado_stock_nuevo_id) REFERENCES estados_stock(id),
    CONSTRAINT fk_stock_mov_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    entidad VARCHAR(80) NOT NULL,
    entidad_id BIGINT UNSIGNED NULL,
    accion VARCHAR(40) NOT NULL,
    usuario_id INT NULL,
    datos_previos JSON NULL,
    datos_nuevos JSON NULL,
    contexto JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_entidad_fecha (entidad, entidad_id, created_at),
    KEY idx_audit_usuario_fecha (usuario_id, created_at),
    KEY idx_audit_accion_fecha (accion, created_at),
    CONSTRAINT fk_audit_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER $$

DROP PROCEDURE IF EXISTS add_index_if_missing $$
CREATE PROCEDURE add_index_if_missing(
    IN p_schema VARCHAR(64),
    IN p_table VARCHAR(64),
    IN p_index VARCHAR(64),
    IN p_ddl TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = p_schema
          AND table_name = p_table
          AND index_name = p_index
        LIMIT 1
    ) THEN
        SET @ddl = p_ddl;
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END $$

DELIMITER ;

CALL add_index_if_missing(
    DATABASE(),
    'facturas',
    'idx_facturas_estado_fecha',
    'CREATE INDEX idx_facturas_estado_fecha ON facturas (estado_id, fecha_emision)'
);

CALL add_index_if_missing(
    DATABASE(),
    'facturas',
    'idx_facturas_cliente_fecha',
    'CREATE INDEX idx_facturas_cliente_fecha ON facturas (cliente_id, fecha_emision)'
);

CALL add_index_if_missing(
    DATABASE(),
    'ventas',
    'idx_ventas_estado_fecha',
    'CREATE INDEX idx_ventas_estado_fecha ON ventas (estado_id, fecha)'
);

CALL add_index_if_missing(
    DATABASE(),
    'cuotas',
    'idx_cuotas_estado_vencimiento',
    'CREATE INDEX idx_cuotas_estado_vencimiento ON cuotas (estado, fecha_vencimiento)'
);

CALL add_index_if_missing(
    DATABASE(),
    'vehiculos',
    'idx_vehiculos_stock_marca_modelo',
    'CREATE INDEX idx_vehiculos_stock_marca_modelo ON vehiculos (estado_stock_id, marca, modelo)'
);

CALL add_index_if_missing(
    DATABASE(),
    'pagos',
    'idx_pagos_cliente_fecha',
    'CREATE INDEX idx_pagos_cliente_fecha ON pagos (cliente_id, fecha)'
);

DROP PROCEDURE IF EXISTS add_index_if_missing;
