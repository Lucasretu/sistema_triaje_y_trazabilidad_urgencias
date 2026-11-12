# Pipelines de agregación analítica

import json

from pymongo import MongoClient

# Conexion al servidor local
client = MongoClient("mongodb://localhost:27017/")
historico_db = client["hospital_db"]
datos = historico_db["episodios"]

# Leemos el json
with open("data/migracion_mongo.json", encoding="utf-8") as f:
    historico = json.load(f)

# Borramos todo para que no haya duplicados al insertar
datos.delete_many({})

# Insertamos el hsitorico
resultado = datos.insert_many(historico)
print(f"Documentos insertados: {len(resultado.inserted_ids)}")

# Comprobacion: muestra un documento y el total que hay en la coleccion
print(datos.find_one({}, {"_id": 0}))
print(datos.count_documents({}))