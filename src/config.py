import os

# Variables de entorno y cadenas de conexión
DOWNLOAD_BASE_URL = "http://10.201.59.248:8088/"
UPDATES_API_URL = "http://10.201.59.248:28000/api/v1/urgencias/novedades"

# Dirección del servidor Redis.
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Puerto de conexión de Redis.
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Base de datos de Redis que se utilizará.
REDIS_DB = int(os.getenv("REDIS_DB", "0"))