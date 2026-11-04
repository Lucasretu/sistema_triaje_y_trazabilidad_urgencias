# Script de migración batch inicial a Mongo

import json

from pathlib import Path

import pandas as pd


# partes_clinicos = pd.read_json("partes_clinicos.json")


df= pd.read_csv("data/admisiones_historico.csv")    

def limpiar_admisiones():
    correcion_errores_fechas(df["timestamp_llegada"])
    correcion_errores_fechas(df["timestamp_alta"])
    #df["frecuencia_cardiaca"] = int(df["frecuencia_cardiaca"])
    #df["tension_arterial"] = int(df["tension_arterial"])


    # Duplicados
    df = df.drop_duplicates()

    print(df.isna().sum())

def correcion_errores_frecuencias():
    pass

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

def formato(df):
    df.columns = df.columns.str.strip().str.lower()
    df["id_episodio"] = df["id_episodio"].str.strip().str.upper()
    df["sip_paciente"] = df["sip_paciente"].str.strip().str.upper()
    df["motivo_consulta"] = df["motivo_consulta"].str.strip().str.lower()
    df["destino_alta"] = df["destino_alta"].str.strip().str.lower()

    # Duplicados
    df = df.drop_duplicates()

   