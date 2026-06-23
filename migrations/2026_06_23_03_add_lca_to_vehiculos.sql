-- Etapa segura - Dato LCA en vehiculos
-- Base objetivo inicial: motoagency_desarrollo
--
-- Impacto:
-- - Agrega una columna nullable para guardar el dato LCA de motovehiculos.
-- - No borra datos.
-- - No modifica datos existentes.
-- - No elimina ni renombra columnas/tablas.
--
-- Rollback, si hubiera que revertir esta mejora:
-- ALTER TABLE vehiculos DROP COLUMN lca;

DELIMITER $$

DROP PROCEDURE IF EXISTS add_column_if_missing $$
CREATE PROCEDURE add_column_if_missing(
    IN p_schema VARCHAR(64),
    IN p_table VARCHAR(64),
    IN p_column VARCHAR(64),
    IN p_ddl TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = p_schema
          AND table_name = p_table
          AND column_name = p_column
        LIMIT 1
    ) THEN
        SET @ddl = p_ddl;
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END $$

DELIMITER ;

CALL add_column_if_missing(
    DATABASE(),
    'vehiculos',
    'lca',
    'ALTER TABLE vehiculos ADD COLUMN lca VARCHAR(180) NULL AFTER nro_dnrpa'
);

DROP PROCEDURE IF EXISTS add_column_if_missing;
