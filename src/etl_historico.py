# Script de migración batch inicial a Mongo

# Parte 1: Limpieza de los historicos y exportación a JSON

import json, time


from pathlib import Path

import pandas as pd
import numpy as np

from pymongo import MongoClient
from .config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

# Carpeta de datos, calculada desde la ubicación del script para que funcione
# aunque se ejecute desde otro directorio.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Carga de los historicos
admisiones_historico = None
partes_clinicos = None
# Pone todos los campos de tipo str del csv con un formato normalizado
def formato():
    admisiones_historico["id_episodio"] = admisiones_historico["id_episodio"].str.strip().str.upper()
    admisiones_historico["sip_paciente"] = admisiones_historico["sip_paciente"].str.strip().str.upper()
    admisiones_historico["motivo_consulta"] = admisiones_historico["motivo_consulta"].str.strip().str.lower()
    admisiones_historico["destino_alta"] = admisiones_historico["destino_alta"].str.strip().str.lower()
    admisiones_historico["tension_arterial"] = admisiones_historico["tension_arterial"].str.strip().str.lower()


# Corrige os posibles errores con la frecuencia cardiaca y tension arterial del csv
# Frecuencia Cardiaca: 
#   * Pone todas las FC a float 64 y en caso de no ser posible las vuelve null
#   * Si la FC tiene valores demasiado bajos o altos (incompatibles con la vida o irreales) los cambia a NaN
# Tesion Arterial: 
#   * Pone todas las TC con el mismo formato (xx/xx) y en caso de no ser posible las vuelve null
#   * Si la FC tiene valores irreales o incopatibles con la vida los cambia a pd.NA
def correcion_errores_frecuencias():
    # Frecuencia cardiaca
    admisiones_historico["frecuencia_cardiaca"]=pd.to_numeric(admisiones_historico["frecuencia_cardiaca"],errors="coerce")
    admisiones_historico.loc[(admisiones_historico["frecuencia_cardiaca"]<=0)|(admisiones_historico["frecuencia_cardiaca"]>=321),"frecuencia_cardiaca"]=np.nan

    #Tension Arterial
    admisiones_historico["tension_arterial"]=admisiones_historico["tension_arterial"].str.replace("_", "/", regex=False)
    mascara=admisiones_historico["tension_arterial"].str.fullmatch(r"\d{2,3}/\d{2,3}").eq(True)
    admisiones_historico.loc[~mascara, "tension_arterial"]=pd.NA

# Convierte todas las fechas del csv al tipo datetime
def correcion_formato_fechas(serie):
    raw = serie.replace("N/D", pd.NA)
    formatos = [
    "%d/%m/%Y %I:%M %p",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S"
    ]
    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    for fmt in formatos:
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        resultado = resultado.fillna(parsed)

    serie = resultado

    return serie
   
   

# Elimina los duplicados del csv en funcion del numero de null del registro   
def del_duplicados(df):
    df=df.copy()
    df["n_nulos"]=df.isna().sum(axis=1)
    df = (
        df.sort_values(["n_nulos", "timestamp_alta"], ascending=[True, False])
        .drop_duplicates(subset="id_episodio",keep="first")
        .drop(columns="n_nulos")
        .sort_index()
    )
    return df

def limpiar_admisiones():
    formato()
    correcion_errores_frecuencias()
    admisiones_historico["timestamp_llegada"]=correcion_formato_fechas(admisiones_historico["timestamp_llegada"])
    admisiones_historico["timestamp_alta"]=correcion_formato_fechas(admisiones_historico["timestamp_alta"])
    admisiones_historico.loc[admisiones_historico["timestamp_alta"] < admisiones_historico["timestamp_llegada"], ["timestamp_llegada", "timestamp_alta"]] = pd.NaT
    df_limpio=del_duplicados(admisiones_historico)

    return df_limpio


# Convierte un valor a número; si no se puede, devuelve NaN.
def a_numero(valor):
    try:
        return pd.to_numeric(valor, errors="coerce")
    except (ValueError, TypeError):
        return np.nan

# Limpia los fallos y duplicados del Json
# Elimina los duplicados
# Convierte todas la edades,la temperatura y la saturacion de O2 a float64
# Añade el campo "glucemia_mg_dl" con valor de NaN si no lo tiene
# Si la temperatura y la frecuencia cardiaca tiene valores demasiado bajos o altos (incompatibles con la vida o irreales) los cambia a NaN

def limpiar_partes_Clinicos():
    #Duplicados
    partes_limpios=partes_clinicos.drop_duplicates(subset="_id_parte").copy()
    #formato edad 
    partes_limpios["edad"]=a_numero(partes_limpios["edad"])
    for constantes in partes_limpios["constantes"]:
        # Omite los partes cuyo campo constantes no sea un diccionario.
        if not isinstance(constantes, dict):
            continue
        #formato temperatura y saturacion y añadir la glucemia en caso necesario
        constantes["temperatura_c"]=a_numero(constantes.get("temperatura_c"))
        constantes["saturacion_o2"]=a_numero(constantes.get("saturacion_o2"))
        constantes.setdefault("glucemia_mg_dl", np.nan)
        # Limpieza de errores frecuencia cardiaca
        fc=a_numero(constantes.get("frecuencia_cardiaca_triaje"))
        if pd.notna(fc) and (fc<=0 or fc>=321):
            fc=np.nan
        constantes["frecuencia_cardiaca_triaje"]=fc
        # Limpieza temperatura
        if pd.notna(constantes["temperatura_c"]) and (constantes["temperatura_c"]<=30 or constantes["temperatura_c"]>=43):
            constantes["temperatura_c"]=np.nan
    
    return partes_limpios


def nan_a_none(v):
    return None if pd.isna(v) else v

def a_epoch(ts):
    # Si la fecha no es válida se guarda como None en lugar de romper el ETL.
    try:
        if pd.isna(ts):
            return None
        return pd.to_datetime(ts).timestamp()
    except (ValueError, TypeError):
        return None

def a_texto(ts):
    # Si la fecha no es válida se guarda como None en lugar de romper el ETL.
    try:
        if pd.isna(ts):
            return None
        return pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def construir_ingresos(serie,modulos_cols):
    tri = serie.get("triaje_manchester")
    cons = serie.get("constantes")
    if not isinstance(tri, dict):
        tri = {}
    if not isinstance(cons, dict):
        cons = {}

    # La edad puede venir vacía; en ese caso se guarda como None.
    edad = nan_a_none(serie.get("edad"))
    if edad is not None:
        edad = int(edad)

    datos_triaje = {
    "nivel_manchester": nan_a_none(tri.get("nivel")),
    "color": nan_a_none(tri.get("color")),
    "categoria_patologia": nan_a_none(tri.get("categoria_patologia")),
    "tiempo_max_espera_min": nan_a_none(tri.get("tiempo_max_espera_min")),
    "constantes": {
        "temperatura_c": nan_a_none(a_numero(cons.get("temperatura_c"))),
        "frecuencia_cardiaca": nan_a_none(a_numero(cons.get("frecuencia_cardiaca_triaje"))),
        "tension_arterial": nan_a_none(serie.get("tension_arterial")),
        "saturacion_o2": nan_a_none(a_numero(cons.get("saturacion_o2"))),
        "glucemia_mg_dl": nan_a_none(a_numero(cons.get("glucemia_mg_dl")))
    },
    "antecedentes": serie.get("antecedentes"),
    "alergias": serie.get("alergias"),}

    for col in modulos_cols:
        if isinstance(serie.get(col), dict):
            datos_triaje[col] = serie.get(col)

    return {
        "id_episodio": serie.get("id_episodio"),
        "datos_admision": {
            "sip_paciente": serie.get("sip_paciente"),
            "edad": edad,
            "motivo_consulta": serie.get("motivo_consulta"),
            "timestamp_llegada":a_epoch(serie.get("timestamp_llegada")),
            "fecha_hora_texto": a_texto(serie.get("timestamp_llegada")),
        },
        "datos_triaje": datos_triaje,
    }

def construir_alta(serie):
    return {
        "id_episodio": serie.get("id_episodio"),
        "timestamp_alta":a_epoch(serie.get("timestamp_alta")),
        "fecha_hora_alta": a_texto(serie.get("timestamp_alta")),
        "destino_alta": nan_a_none(serie.get("destino_alta")),
    }

# Une los datos limpios del csv con los del json usando id_episodio como clave
def unir_datos(df_limpio, df_partes):
    # Nos aseguramos de que no queden episodios repetidos antes de cruzar.
    df_limpio = df_limpio.drop_duplicates(subset="id_episodio", keep="first")
    df_partes = df_partes.drop_duplicates(subset="id_episodio", keep="first")

    df_final = pd.merge(df_limpio, df_partes, on=["id_episodio", "sip_paciente"], how="inner")

    # Avisa de los episodios que no tienen parte clínico y no se pueden migrar.
    print(f"Episodios sin parte clínico (descartados): {len(df_limpio) - len(df_final)}")

    modulos_cols = [c for c in df_final if c.startswith("modulo_")]
    mask_alta = df_final["timestamp_alta"].notna()

    nuevos = [construir_ingresos(r,modulos_cols) for _, r in df_final[~mask_alta].iterrows()]
    altas  = [construir_alta(r)   for _, r in df_final[mask_alta].iterrows()]

    resultado = {
    "timestamp_consulta": time.time(),
    "total_nuevos": len(nuevos),
    "total_altas": len(altas),
    "nuevos_ingresos": nuevos,
    "pacientes_alta": altas,
    }
    
    return resultado

# Guarda el resultado en un json
def exportar_json(resultado):
    with open(DATA_DIR / "migracion_mongo.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False, default=str)
 


def main_1():
    # Indicamos que main_1() va a cargar los datos en esas variables compartidas, para que las demás funciones puedan utilizarlas.
    global admisiones_historico, partes_clinicos
 
    # Carga los archivos históricos.
    admisiones_historico = pd.read_csv(DATA_DIR / "admisiones_historico.csv")
    partes_clinicos = pd.read_json(DATA_DIR / "partes_clinicos.json")

    # Comprueba que el CSV tenga las columnas esperadas antes de limpiarlo.
    columnas = ["id_episodio", "sip_paciente", "timestamp_llegada", "timestamp_alta",
                "motivo_consulta", "frecuencia_cardiaca", "tension_arterial", "destino_alta"]
    faltan = [c for c in columnas if c not in admisiones_historico.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el CSV: {faltan}")
 
    # Limpia los datos de ambos archivos.
    df_limpio = limpiar_admisiones()
    df_partes = limpiar_partes_Clinicos()
 
    # Une los datos y genera el resultado.
    df_final = unir_datos(df_limpio, df_partes)
 
    # Exporta el resultado a JSON.
    exportar_json(df_final)
 
    print("Exportación del histórico a JSON completada.") 

# Parte 2: Migración de los historicos a MongoDB
def main_2():
    
 
    main_1()
 
    df_limpio = limpiar_admisiones()
    df_partes = limpiar_partes_Clinicos()

    # Evita que un episodio repetido detenga toda la migración.
    df_limpio = df_limpio.drop_duplicates(subset="id_episodio", keep="first")
    df_partes = df_partes.drop_duplicates(subset="id_episodio", keep="first")

    df_final = pd.merge(
        df_limpio,
        df_partes,
        on=["id_episodio", "sip_paciente"],
        how="inner",
    )
 
    modulos_cols = [c for c in df_final if c.startswith("modulo_")]
 
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
 
    try:
        historico_db = client[MONGO_DB]
        datos = historico_db[MONGO_COLLECTION]
 
        documentos = []
 
        for _, serie in df_final.iterrows():
            documento = construir_ingresos(serie, modulos_cols)
 
            if pd.notna(serie["timestamp_alta"]):
                documento["datos_alta"] = {
                    "timestamp_alta": a_epoch(serie["timestamp_alta"]),
                    "fecha_hora_alta": a_texto(serie["timestamp_alta"]),
                    "destino_alta": nan_a_none(serie["destino_alta"]),
                }
 
            documentos.append(documento)
 
        for documento in documentos:
            datos.update_one(
                {"id_episodio": documento["id_episodio"]},
                {"$set": documento},
                upsert=True
            )
 
        print(f"Documentos migrados a MongoDB: {len(documentos)}")
 
    finally:
        client.close()

if __name__ == "__main__":
    main_1()