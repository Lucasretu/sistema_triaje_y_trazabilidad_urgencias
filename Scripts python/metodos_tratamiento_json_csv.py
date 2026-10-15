import pandas as pd

#lectura de los historicos con panda
admisiones_historico = pd.read_csv("admisiones_historico.csv")
partes_clinicos= pd.read_json("partes_clinicos.json")
numero=1
for line in admisiones_historico:
    print(str(numero)+" "+line)
    numero=numero+1
print(type(admisiones_historico))
