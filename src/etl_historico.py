import json

from pathlib import Path

import pandas as pd


# partes_clinicos = pd.read_json("partes_clinicos.json")

def limpiar_admisiones():
    #Lectura de los historicos con panda
    df = pd.read_csv("../data/admisiones_historico.csv")
    print("CSV leido (comprobacion)", len(df), " registros")

    # Nombres de columnas en minusculas y sin espacios
    df.columns = df.columns.str.strip().str.lower()
    print("Columnas limpiadas (comprobacion)")

    # Normalizar textos de las columnas
    df["id_episodio"] = df["id_episodio"].str.strip().str.upper()
    df["sip_paciente"] = df["sip_paciente"].str.strip().str.upper()
    df["timestamp_llegada"] = df["timestamp_llegada"].to_timestamp()
    df["timestamp_alta"] = df["timestamp_alta"].to_timestamp()
    df["motivo_consulta"] = df["motivo_consulta"].str.strip().str.lower()
    df["frecuencia_cardiaca"] = int(df["frecuencia_cardiaca"])
    df["tension_arterial"] = int(df["tension_arterial"])
    df["destino_alta"] = df["destino_alta"].str.strip().str.lower()

    # Duplicados
    df = df.drop_duplicates()

   