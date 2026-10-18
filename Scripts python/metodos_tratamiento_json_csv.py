import pandas as pd

#lectura de los historicos con panda
df = pd.read_csv("Base de datos/admisiones_historico.csv")


mascara_duplicados_id= df.duplicated(subset="id_episodio",keep=False)

print(df["timestamp_llegada"])
#if mascara_duplicados_id.any:
   
 #   df_cuarentena = df[mascara_duplicados_id].sort_values(by="id_episodio")
 #   print(df_cuarentena)

#  df["_complitud"]=df.notna().sum(axis=1)

#    df = (
#        df.sort_values(
#            by=["cliente_id", "_completitud", "fecha_alta"],
#            ascending=[True, False, False]
#        )
#        .drop_duplicates(subset=["cliente_id"], keep="first")
#        .drop(columns=["_completitud"])
#        .reset_index(drop=True)
#    )
#    print(f"/nDataFrame tras consolidar unicidad de claves: {len(df)} registros válidos.")