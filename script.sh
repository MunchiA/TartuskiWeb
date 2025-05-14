#!/bin/bash
read -p "Por favor, ingrese el endpoint de la base de datos: " ENDPOINT
ENDPOINT=""
USER="admin"
PASSWORD="tartuski"
DATABASE="aurora_sql_tartuski"

echo "DB_HOST=$ENDPOINT" >> .env
# Comandos SQL a ejecutar
SQL_COMMANDS=$(cat <<EOF
USE ${DATABASE};


CREATE TABLE IF NOT EXISTS usuarios (
    azure_user_id VARCHAR(255) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    PRIMARY KEY (azure_user_id)
);

CREATE TABLE IF NOT EXISTS eventos (
    id INT NOT NULL AUTO_INCREMENT,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME NOT NULL,
    azure_user_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (azure_user_id)
        REFERENCES usuarios(azure_user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
EOF
)
# Ejecutar los comandos
mysql -h "$ENDPOINT" -u "$USER" -p"$PASSWORD" -e "$SQL_COMMANDS"

# Crear el archivo de configuración de Gunicorn
cat << 'EOF_CONF' > gunicorn.conf.py
bind = '0.0.0.0:8000'
workers = 3
timeout = 120
EOF_CONF

# Iniciar Gunicorn
gunicorn -c gunicorn.conf.py app:app &
