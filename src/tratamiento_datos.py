import pandas as pd

#Lectura de los historicos con panda
admisiones_historico = pd.read_csv("admisiones_historico.csv")
partes_clinicos = pd.read_json("partes_clinicos.json")

admisiones_historico.head(10)
partes_clinicos.head(10)
