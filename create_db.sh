#!/usr/bin/env bash

# Comprobamos que nos pasen al menos un argumento
if [ $# -lt 1 ]; then
  echo "Uso: $0 <host_mysql>"
  exit 1
fi

# Parámetro posicional: primer argumento es el host
MYSQL_HOST="$1"

# Datos fijos de conexión
MYSQL_USER="admin"
MYSQL_PASS="tartuski"

# Conectamos y ejecutamos las sentencias SQL
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" <<EOF
USE aurora_sql_tartuski;

CREATE TABLE IF NOT EXISTS usuarios (
    azure_user_id VARCHAR(255) NOT NULL,
    nombre        VARCHAR(255) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    PRIMARY KEY (azure_user_id)
);

CREATE TABLE IF NOT EXISTS eventos (
    id             INT NOT NULL AUTO_INCREMENT,
    titulo         VARCHAR(255) NOT NULL,
    descripcion    TEXT,
    fecha_inicio   DATETIME NOT NULL,
    fecha_fin      DATETIME NOT NULL,
    azure_user_id  VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (azure_user_id)
        REFERENCES usuarios(azure_user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
EOF