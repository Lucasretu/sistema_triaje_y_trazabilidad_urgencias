# Scrip principal de la aplicación

import time
from threading import Thread

from urgencias_worker import check_updates
from etl_historico import main_1 as etl_main
from etl_historico import main_2 as mongo_main

def nuevos_datos():
    while True:
        check_updates()
        time.sleep(5)

Thread(target=nuevos_datos, daemon=True).start()


print("Iniciando la aplicación...")

time.sleep(1)

print("Menu principal de la aplicación")

print()

while True:
    print("Seleccione una opción:")
    print("1. Exportacion de historico a JSON")
    print("2. Insercion del JSON en MongoDB")
    print("3. Consulta de datos en MongoDB (aun no implementada)")
    print("4. Polling de la API (aun no implementada)")
    print("5. Salir")

    opcion = input("Ingrese el número de la opción deseada: ")

    if opcion == "1":
        # Llamamos a la funcion principal del script del ETL para limpiar los datos y exportarlos a JSON
        etl_main()
        print("Exportación de historico a JSON completada.")
    elif opcion == "2":
        # Llamamos a la funcion principal del script del ETL para insertar el JSON en MongoDB
        mongo_main()
        print("Inserción del JSON en MongoDB completada.")
    elif opcion == "3":
        print("Opción 3 seleccionada. Esta opción aún no está implementada.")
    elif opcion == "4":
        print("Saliendo del programa...")
    elif opcion == "5":
        print("Saliendo del programa...")
        break
    else:
        print("Opción inválida. Por favor, ingrese un número válido.")
