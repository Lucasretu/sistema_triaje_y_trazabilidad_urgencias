# Consultas sobre los episodios guardados en MongoDB.
#
# Correcciones respecto a la versión anterior:
#  * Se conectaba a "mongodb://localhost:27017" sin usuario ni contraseña.
#    Ahora se reutiliza mongo_client (src/urgencias_worker.py), que ya coge
#    la URI con credenciales de src/config.py.
#  * Se leía la base de datos "urgencias" y el campo "alta". La opción 2 del
#    menú y el worker en tiempo real guardan en "hospital_db" y en "datos_alta".
#  * Se ha eliminado cargar(): los datos ya los inserta la opción 2 y, además,
#    hacía un col.drop() que borraba la colección. También esperaba otro
#    formato de JSON (nuevos_ingresos / pacientes_alta).

from .urgencias_worker import mongo_client

# Colección que rellenan la opción 2 del menú y el procesamiento en tiempo real.
col = mongo_client["hospital_db"]["episodios"]


# ------------------------------------------------------------------
# Consulta 1: tiempo medio de estancia (min) por categoría patológica
# ------------------------------------------------------------------
def consulta_1():
    pipeline = [
        {"$match": {"datos_alta.timestamp_alta": {"$exists": True}}},
        {"$project": {
            "categoria": "$datos_triaje.categoria_patologia",
            # los timestamps son epoch en segundos -> /60 para minutos
            "estancia_min": {"$divide": [
                {"$subtract": ["$datos_alta.timestamp_alta",
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
    return {"$sum": {"$cond": [{"$eq": ["$datos_alta.destino_alta", destino]}, 1, 0]}}


def consulta_2():
    pipeline = [
        {"$match": {"datos_alta.destino_alta": {"$in": ["domicilio", "ingreso_planta"]}}},
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


# Muestra por pantalla las dos consultas de forma sencilla.
def mostrar_consultas():
    print()
    print("1) Estancia media por categoría patológica")
    resultados = consulta_1()
    if len(resultados) == 0:
        print("   No hay datos. Ejecuta antes las opciones 1 y 2 del menú.")
    else:
        for r in resultados:
            print(f"   {str(r['categoria']):<15} {r['estancia_media_min']:>8.2f} min   (n={r['n_episodios']})")

    print()
    print("2) Destino al alta por grupo de edad (domicilio vs ingreso en planta)")
    resultados = consulta_2()
    if len(resultados) == 0:
        print("   No hay datos. Ejecuta antes las opciones 1 y 2 del menú.")
    else:
        for r in resultados:
            print(f"   {r['grupo_edad']:<6} domicilio {r['pct_domicilio']:>5}% | "
                  f"planta {r['pct_ingreso_planta']:>5}%   (n={r['total']})")
    print()


if __name__ == "__main__":
    mostrar_consultas()
