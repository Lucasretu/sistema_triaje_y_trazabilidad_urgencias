# Script de migración batch inicial a Mongo

import json
import re

from pathlib import Path

import pandas as pd
import numpy as np


# partes_clinicos = pd.read_json("partes_clinicos.json")


df= pd.read_csv("data/admisiones_historico.csv")    

def limpiar_admisiones():
    formato()
    correcion_errores_fechas(df["timestamp_llegada"])
    correcion_errores_fechas(df["timestamp_alta"])
    print(df.duplicated().sum())
    df_limpio=del_duplicados(df)
    print(df_limpio.duplicated().sum())

    df_limpio.to_csv("limpio.csv",index=False)   

def correcion_errores_frecuencias():
    # Frecuencia cardiaca
    df["frecuencia_cardiaca"]=pd.to_numeric(df["frecuencia_cardiaca"],errors="coerce")
    df.loc[(df["frecuencia_cardiaca"]<=0)|(df["frecuencia_cardiaca"]>=321),"frecuencia_cardiaca"]=np.nan

    #Tension Arterial
    df["tension_arterial"]=df["tension_arterial"].str.replace("_", "/", regex=False)
    mascara=df["tension_arterial"].str.fullmatch(r"\d{2,3}/\d{2,3}").fillna(False)
    df.loc[~mascara, "tension_arterial"]=pd.NA

def correcion_errores_fechas(serie):
    raw = serie.replace("N/D", pd.NA)
    formatos = [
    "%d/%m/%Y %I:%M %p",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S"
    ]
    resultado = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for fmt in formatos:
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        resultado = resultado.fillna(parsed)

    serie = resultado

def formato():
    df["id_episodio"] = df["id_episodio"].str.strip().str.upper()
    df["sip_paciente"] = df["sip_paciente"].str.strip().str.upper()
    df["motivo_consulta"] = df["motivo_consulta"].str.strip().str.lower()
    df["destino_alta"] = df["destino_alta"].str.strip().str.lower()
    df["tension_arterial"] = df["tension_arterial"].str.strip().str.lower()
    
def del_duplicados(df):
    # Duplicados
    df["n_nulos"]=df.isna().sum(axis=1)
    df = (
        df.sort_values(["n_nulos", "timestamp_alta"], ascending=[True, False])
        .drop_duplicates(subset="id_episodio",keep="first")
        .drop(columns="n_nulos")
        .sort_index()
    )

    return df

def limpiar_partes_Clinicos():
    pass


df_json=pd.read_json("data/partes_clinicos.json")

def correccion_constantes():
    df_json["edad"]=pd.to_numeric(df_json["edad"],errors="coerce")
    
    for constantes in df_json["constantes"]:
        constantes["temperatura_c"]=pd.to_numeric(constantes["temperatura_c"],errors="coerce")
        constantes["saturacion_o2"]=pd.to_numeric(constantes["saturacion_o2"],errors="coerce")
        constantes.setdefault("glucemia_mg_dl", np.nan)
        if(constantes["frecuencia_cardiaca_triaje"]<=0 or constantes["frecuencia_cardiaca_triaje"]>=321):
           constantes["frecuencia_cardiaca_triaje"]=np.nan
        if(constantes["temperatura_c"]<=30 or constantes["temperatura_c"]>=43):
            constantes["temperatura_c"]=np.nan
        
#print(df_json["constantes"].head(393))
correccion_constantes()