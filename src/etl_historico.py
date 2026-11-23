# Script de migración batch inicial a Mongo

# Parte 1: Limpieza de los historicos y exportación a JSON

import json, time
import re

from pathlib import Path

import pandas as pd
import numpy as np


# Carga de los historicos
admisiones_historico= pd.read_csv("data/admisiones_historico.csv")
partes_clinicos=pd.read_json("data/partes_clinicos.json")    

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
    mascara=admisiones_historico["tension_arterial"].str.fullmatch(r"\d{2,3}/\d{2,3}").fillna(False)
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
    resultado = pd.Series(pd.NaT, index=admisiones_historico.index, dtype="datetime64[ns]")
    for fmt in formatos:
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        resultado = resultado.fillna(parsed)

    serie = resultado

    return serie
   
   

# Elimina los duplicados del csv en funcion del numero de null del registro   
def del_duplicados(df):
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
    admisiones_historico["timestamp_llegada"]=correcion_formato_fechas(admisiones_historico["timestamp_llegada"])
    admisiones_historico["timestamp_alta"]=correcion_formato_fechas(admisiones_historico["timestamp_alta"])
    admisiones_historico.loc[admisiones_historico["timestamp_alta"] < admisiones_historico["timestamp_llegada"], ["timestamp_llegada", "timestamp_alta"]] = pd.NaT
    print(admisiones_historico.duplicated().sum())
    df_limpio=del_duplicados(admisiones_historico)

    return df_limpio

# Limpia los fallos y duplicados del Json
# Elimina los duplicados
# Convierte todas la edades,la temperatura y la saturacion de O2 a float64
# Añade el campo "glucemia_mg_dl" con valor de NaN si no lo tiene
# Si la temperatura y la frecuencia cardiaca tiene valores demasiado bajos o altos (incompatibles con la vida o irreales) los cambia a NaN

def limpiar_partes_Clinicos():
    #Duplicados
    partes_clinicos.drop_duplicates(subset="_id_parte")
    #formato edad 
    partes_clinicos["edad"]=pd.to_numeric(partes_clinicos["edad"],errors="coerce")   
    for constantes in partes_clinicos["constantes"]:
        #formato temperatura y saturacion y añadir la glucemia en caso necesario
        constantes["temperatura_c"]=pd.to_numeric(constantes["temperatura_c"],errors="coerce")
        constantes["saturacion_o2"]=pd.to_numeric(constantes["saturacion_o2"],errors="coerce")
        constantes.setdefault("glucemia_mg_dl", np.nan)
        # Limpieza de errores frecuencia cardiaca
        if(constantes["frecuencia_cardiaca_triaje"]<=0 or constantes["frecuencia_cardiaca_triaje"]>=321):
            constantes["frecuencia_cardiaca_triaje"]=np.nan
        # Limpieza temperatura
        if(constantes["temperatura_c"]<=30 or constantes["temperatura_c"]>=43):
            constantes["temperatura_c"]=np.nan
    
    return partes_clinicos


def nan_a_none(v):
    return None if pd.isna(v) else v

def a_epoch(ts):
    if pd.isna(ts):
        return None
    return pd.to_datetime(ts).timestamp()

def a_texto(ts):
    if pd.isna(ts):
        return None
    return pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M:%S")




def construir_ingresos(serie,modulos_cols):
    tri, cons = serie["triaje_manchester"], serie["constantes"]

    datos_triaje = {
    "nivel_manchester": tri["nivel"],
    "color": tri["color"],
    "categoria_patologia": tri["categoria_patologia"],
    "tiempo_max_espera_min": tri["tiempo_max_espera_min"],
    "constantes": {
        "temperatura_c": nan_a_none(cons.get("temperatura_c")),
        "frecuencia_cardiaca": nan_a_none(cons.get("frecuencia_cardiaca_triaje")),
        "tension_arterial": nan_a_none(serie["tension_arterial"]),
        "saturacion_o2": nan_a_none(cons.get("saturacion_o2")),
        "glucemia_mg_dl": nan_a_none(cons.get("glucemia_mg_dl"))
    },
    "antecedentes": serie["antecedentes"],
    "alergias": serie["alergias"],}

    for col in modulos_cols:
        if isinstance(serie[col], dict):
            datos_triaje[col] = serie[col]

    return {
        "id_episodio": serie["id_episodio"],
        "datos_admision": {
            "sip_paciente": serie["sip_paciente"],
            "edad": int(serie["edad"]),
            "motivo_consulta": serie["motivo_consulta"],
            "timestamp_llegada":a_epoch(serie["timestamp_llegada"]),
            "fecha_hora_texto": a_texto(serie["timestamp_llegada"]),
        },
        "datos_triaje": datos_triaje,
    }

def construir_alta(serie):
    return {
        "id_episodio": serie["id_episodio"],
        "timestamp_alta":a_epoch(serie["timestamp_alta"]),
        "fecha_hora_alta": a_texto(serie["timestamp_alta"]),
        "destino_alta": nan_a_none(serie["destino_alta"]),
    }

# Une los datos limpios del csv con los del json usando id_episodio como clave
def unir_datos(df_limpio, df_partes):
    
    df_final = pd.merge(df_limpio, df_partes, on=["id_episodio", "sip_paciente"], how="inner", validate="one_to_one",)

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
    with open("data/migracion_mongo.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False, default=str)
 
# Ejecucion del script
df_limpio = limpiar_admisiones()
df_partes = limpiar_partes_Clinicos()
df_final = unir_datos(df_limpio, df_partes)
exportar_json(df_final)

main_1()

# Parte 2: Migración de los historicos a MongoDB

import json

from pymongo import MongoClient

# Conexion al servidor local
client = MongoClient("mongodb://localhost:27017/")
historico_db = client["hospital_db"]
datos = historico_db["episodios"]

# Leemos el json
with open("data/migracion_mongo.json", encoding="utf-8") as f:
    historico = json.load(f)

def main_2():
    # Borramos todo para que no haya duplicados al insertar
    datos.delete_many({})
    # Insertamos el hsitorico
    datos.insert_many(historico)

main_2()