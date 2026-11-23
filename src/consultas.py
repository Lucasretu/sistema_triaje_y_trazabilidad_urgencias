import json
import os
from pathlib import Path

from pymongo import MongoClient

RUTA_JSON = Path(__file__).resolve().parent / "data" / "episodios_urgencias.json"
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                     serverSelectionTimeoutMS=5000)
col = client["urgencias"]["episodios"]


# ------------------------------------------------------------------
# 0. Carga: una colección con un documento por episodio
#    (ingreso + triaje + alta embebida en el campo "alta")
# ------------------------------------------------------------------
def cargar():
    with open(RUTA_JSON, encoding="utf-8") as f:
        datos = json.load(f)
    altas = {a["id_episodio"]: a for a in datos["pacientes_alta"]}

    docs = []
    for ing in datos["nuevos_ingresos"]:
        doc = dict(ing)
        a = altas.get(ing["id_episodio"])
        if a:
            doc["alta"] = {k: v for k, v in a.items() if k != "id_episodio"}
        doc["_id"] = ing["id_episodio"]
        docs.append(doc)

    col.drop()  # idempotente: se puede relanzar sin duplicar
    col.insert_many(docs)
    print(f"Cargados {col.count_documents({})} episodios\n")


# ------------------------------------------------------------------
# Consulta 1: tiempo medio de estancia (min) por categoría patológica
# ------------------------------------------------------------------
def consulta_1():
    pipeline = [
        {"$match": {"alta.timestamp_alta": {"$exists": True}}},
        {"$project": {
            "categoria": "$datos_triaje.categoria_patologia",
            # los timestamps son epoch en segundos -> /60 para minutos
            "estancia_min": {"$divide": [
                {"$subtract": ["$alta.timestamp_alta",
                               "$datos_admision.timestamp_llegada"]}, 60]},
        }},
        {"$group": {"_id": "$categoria",
                    "estancia_media_min": {"$avg": "$estancia_min"},
                    "n_episodios": {"$sum": 1}}},
        {"$project": {"_id": 0, "categoria": "$_id", "n_episodios": 1,
                      "estancia_media_min": {"$round": ["$estancia_media_min", 2]}}},
        {"$sort": {"estancia_media_min": -1}},
    ]
    return list(col.aggregate(pipeline))


# ------------------------------------------------------------------
# Consulta 2: % domicilio vs ingreso en planta por grupo de edad
#   (el % se calcula sobre los episodios que acaban en alguno de esos
#    dos destinos dentro de cada grupo)
# ------------------------------------------------------------------
LIMITES = [0, 15, 35, 50, 65, 80, 130]
ETIQUETAS = {0: "0-14", 15: "15-34", 35: "35-49", 50: "50-64", 65: "65-79", 80: "80+"}


def _cuenta(destino):
    return {"$sum": {"$cond": [{"$eq": ["$alta.destino_alta", destino]}, 1, 0]}}


def consulta_2():
    pipeline = [
        {"$match": {"alta.destino_alta": {"$in": ["domicilio", "ingreso_planta"]}}},
        {"$bucket": {
            "groupBy": "$datos_admision.edad",
            "boundaries": LIMITES,           # [a, b) -> 14 cae en 0-14, 15 en 15-34
            "default": "fuera_de_rango",
            "output": {"total": {"$sum": 1},
                       "n_domicilio": _cuenta("domicilio"),
                       "n_ingreso_planta": _cuenta("ingreso_planta")},
        }},
        {"$project": {
            "_id": 1, "total": 1, "n_domicilio": 1, "n_ingreso_planta": 1,
            "pct_domicilio": {"$round": [
                {"$multiply": [{"$divide": ["$n_domicilio", "$total"]}, 100]}, 1]},
            "pct_ingreso_planta": {"$round": [
                {"$multiply": [{"$divide": ["$n_ingreso_planta", "$total"]}, 100]}, 1]},
        }},
    ]
    res = list(col.aggregate(pipeline))  # $bucket ya devuelve los grupos ordenados
    for r in res:
        r["grupo_edad"] = ETIQUETAS.get(r.pop("_id"), "fuera_de_rango")
    return res


if __name__ == "__main__":
    cargar()

    print("1) Estancia media por categoría patológica")
    for r in consulta_1():
        print(f"   {r['categoria']:<15} {r['estancia_media_min']:>8.2f} min   (n={r['n_episodios']})")

    print("\n2) Destino al alta por grupo de edad (domicilio vs ingreso en planta)")
    for r in consulta_2():
        print(f"   {r['grupo_edad']:<6} domicilio {r['pct_domicilio']:>5}% | "
              f"planta {r['pct_ingreso_planta']:>5}%   (n={r['total']})")